-- ****************************************************************************
-- SCHEMA DE LA PLATEFORME DE BENCHMARKING (SPIDER-READY)
-- ****************************************************************************

-- Extension pour la génération automatique d'UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. GESTION DE L'ÉVÉNEMENT ET DES ÉQUIPES
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS hackathon (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS participants (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    hackathon_id uuid REFERENCES hackathon(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    api_key_hash TEXT UNIQUE, -- Pour l'authentification des requêtes de benchmark
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table de liaison pour les membres d'équipes
CREATE TABLE IF NOT EXISTS team_members (
    team_id uuid REFERENCES teams(id) ON DELETE CASCADE,
    participant_id uuid REFERENCES participants(id) ON DELETE CASCADE,
    PRIMARY KEY (team_id, participant_id)
);

-- 2. GESTION DU DATASET (Banque de questions et données)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS data_contexts (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,               -- ex: 'university', 'world_1'
    schema_definition JSONB,          -- Description des tables/colonnes pour les prompts
    storage_link TEXT NOT NULL,       -- Chemin local ou URL vers le fichier .sqlite/.csv
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,         
    gold_code TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('SQL', 'Python')),
    category TEXT,                    -- join, aggregate, cleaning, filtering, sorting...
    difficulty TEXT CHECK (difficulty IN ('easy', 'medium', 'hard', 'extra_hard')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Liaison Many-to-Many entre questions et contextes de données
CREATE TABLE IF NOT EXISTS question_data_contexts (
    question_id uuid REFERENCES questions(id) ON DELETE CASCADE,
    context_id uuid REFERENCES data_contexts(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, context_id)
);

-- 3. RÉSULTATS ET MÉTRIQUES (Historique des Benchmarks)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluations (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id uuid REFERENCES teams(id) ON DELETE CASCADE,
    session_id uuid NOT NULL,         -- Pour grouper les questions d'un même run
    language TEXT NOT NULL CHECK (language IN ('SQL', 'Python')),
    model_name TEXT,                  -- ex: 'gpt-3.5-turbo', 'llama-3-8b'
    status TEXT DEFAULT 'pending',    -- pending, running, completed, failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_results (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id uuid REFERENCES evaluations(id) ON DELETE CASCADE,
    question_id uuid REFERENCES questions(id),
    
    -- Résultats techniques
    generated_code TEXT,
    is_correct BOOLEAN DEFAULT FALSE, -- Gold Standard
    silver_score FLOAT DEFAULT 0.0,   -- Score de proximité (variables locales)
    
    -- Métriques de performance
    generation_duration FLOAT,        -- Temps de réponse du LLM (secondes)
    execution_metrics JSONB,          -- {cpu_usage, ram_usage_mb, duration_ms, error_msg}
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour accélérer les recherches fréquentes (Leaderboards et Historiques)
CREATE INDEX idx_evaluations_team ON evaluations(team_id);
CREATE INDEX idx_task_results_eval ON task_results(evaluation_id);
CREATE INDEX idx_questions_category ON questions(category);