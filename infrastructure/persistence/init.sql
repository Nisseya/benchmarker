CREATE TABLE IF NOT EXISTS hackathon(
    id uuid,
    name TEXT,
    date TEXT,
)

CREATE TABLE IF NOT EXISTS participants(
    id uuid,
    last_name TEXT,
    first_name TEXT,
)

CREATE TABLE IF NOT EXISTS teams(
    id uuid,
    name TEXT,
    created_at timestamps,
)

CREATE TABLE IF NOT EXISTS evaluations(
    id uuid,
    team_id uuid references team.id,
    language TEXT (either SQL or Python),
    created_at timestamps,
)

CREATE TABLE IF NOT EXISTS task_results(
    id uuid,
    evaluation_id uuid references evaluations.id
    generated_code TEXT,
    generation_duration float,
    execution_metrics JSONB, -- contains CPU usage, duration, RAM usage etc, maybe add if some are good to capture too 
    created_at timestamps,
)


CREATE TABLE IF NOT EXISTS tables(
    id uuid, 
    name TEXT,
    schema JSONB,
    link? --something to get access to the table, uing either SQL or python
)

CREATE TABLE IF NOT EXISTS questions_tables(
    question_id uuid references questions.id,
    table_id uuid references tables.id
)

CREATE TABLE IF NOT EXISTS questions(
    id uuid, 
    content TEXT,
    category TEXT, --join, aggregate, cleaning, filtering, sorting etc
    difficulty TEXT, --easy, medium, hard
)

----------------
----------------
----------------

-- Extension pour la génération automatique d'UUID (optionnel mais recommandé)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS hackathon (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    hackathon_id uuid REFERENCES hackathon(id), -- Pour lier l'équipe à l'événement
    name TEXT NOT NULL,
    api_key_hash TEXT, -- Sécurité pour l'accès API
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluations (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id uuid REFERENCES teams(id) ON DELETE CASCADE,
    model_name TEXT, -- Pour savoir quel modèle (Llama, Mistral...) a été testé
    language TEXT CHECK (language IN ('SQL', 'Python')), 
    status TEXT DEFAULT 'running', -- pending, running, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_results (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id uuid REFERENCES evaluations(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL, -- Référence à l'ID de la question Spider
    generated_code TEXT,
    is_correct BOOLEAN, -- Gold Standard
    silver_score FLOAT, -- Ton Silver Standard (0 à 1)
    generation_duration FLOAT, -- Temps de réponse du LLM
    execution_metrics JSONB, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-----------

-- Champ,Description,Intérêt
-- cpu_peak_percent,Pic d'utilisation CPU durant l'exécution.,Détecter les codes inefficaces (boucles mal optimisées).
-- ram_peak_mb,Pic de consommation RAM.,Crucial pour le benchmark Spider (gestion de gros datasets).
-- execution_duration_ms,Temps d'exécution pur du code.,Différent de la durée de génération du LLM.
-- io_read_count,Nombre de lectures disque.,Voir si le modèle abuse des accès fichiers.
-- error_type,"SyntaxError, Timeout, MemoryError.",Pour catégoriser les échecs des petits modèles.
-- tokens_count,Nombre de tokens générés.,Pour calculer le coût réel de l'évaluation.