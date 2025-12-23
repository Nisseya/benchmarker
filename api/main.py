from fastapi import FastAPI, Depends, BackgroundTasks
from sqlalchemy.orm import Session

# Import des couches
from infrastructure.database import get_db
from infrastructure.adapters.repository.postgres_repository import PostgresRepository
from infrastructure.adapters.cloud.runpod_adapter import RunPodAdapter
from domain.services.benchmark_service import BenchmarkService

app = FastAPI(title="Hackathon Benchmark Platform")

# --- Fonctions d'Injection ---

def get_benchmark_service(db: Session = Depends(get_db)) -> BenchmarkService:
    # 1. On crée l'adaptateur de persistance avec la session DB actuelle
    repo = PostgresRepository(db)
    
    # 2. On crée les autres adaptateurs (Cloud, Executeur, etc.)
    cloud = RunPodAdapter(api_key="TON_API_KEY")
    
    # 3. On injecte tout dans le service de domaine
    return BenchmarkService(repository=repo, cloud=cloud)

# --- Routes API ---

@app.post("/benchmarks/run/{team_id}")
async def run_evaluation(
    team_id: str, 
    model_name: str,
    background_tasks: BackgroundTasks,
    service: BenchmarkService = Depends(get_benchmark_service)
):
    """
    Lance un benchmark pour une équipe. 
    On utilise BackgroundTasks pour rendre la main au frontend immédiatement.
    """
    # Création de la session d'évaluation dans le domaine
    session_id = service.init_session(team_id, model_name)
    
    # Lancement du processus lourd en arrière-plan
    background_tasks.add_task(service.run_full_benchmark, session_id)
    
    return {
        "status": "started",
        "session_id": session_id,
        "message": "Le benchmark est en cours. Suivez les progrès via WebSocket."
    }

@app.get("/leaderboard")
async def get_leaderboard(service: BenchmarkService = Depends(get_benchmark_service)):
    return service.get_global_leaderboard()