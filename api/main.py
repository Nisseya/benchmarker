import os
from uuid import UUID
from typing import List

from fastapi import FastAPI, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

# Database & Infrastructure
from infrastructure.database import get_db
from infrastructure.adapters.repository.postgres_repository import PostgresRepository
from infrastructure.adapters.cloud.runpod_adapter import RunPodAdapter
from infrastructure.adapters.cloud.local_cloud_adapter import LocalCloudAdapter
from infrastructure.adapters.llm.openai_adapter import OpenAIAdapter
from infrastructure.adapters.notifier.websocket_notifier import ConnectionManager, WebSocketNotifier

# Domain Services
from domain.services.benchmark_service import BenchmarkService
from domain.services.dataset_service import DatasetService

app = FastAPI(title="Hackathon Benchmark Platform")

# --- Initialisation des Singletons d'Infrastructure ---

# Le manager de connexions WebSocket doit être unique
ws_manager = ConnectionManager()

# --- Fonctions d'Injection (Dependencies) ---

def get_repository(db: Session = Depends(get_db)) -> PostgresRepository:
    return PostgresRepository(db)

def get_cloud_adapter():
    """Sélectionne l'adaptateur Cloud selon l'environnement."""
    env = os.getenv("APP_ENV", "local")
    if env == "production":
        return RunPodAdapter(
            api_key=os.getenv("RUNPOD_API_KEY","none"), 
            worker_image=os.getenv("WORKER_IMAGE_URL","none")
        )
    return LocalCloudAdapter(image_name="benchmark-worker-local")

def get_llm_adapter():
    """Initialise l'adaptateur pour la génération de code."""
    return OpenAIAdapter(api_key=os.getenv("OPENAI_API_KEY","none"))

def get_dataset_service(repo: PostgresRepository = Depends(get_repository)) -> DatasetService:
    return DatasetService(repository=repo)

def get_benchmark_service(
    repo: PostgresRepository = Depends(get_repository),
    cloud = Depends(get_cloud_adapter),
    llm = Depends(get_llm_adapter)
) -> BenchmarkService:
    # On injecte le notifier WebSocket lié au manager global
    notifier = WebSocketNotifier(ws_manager)
    return BenchmarkService(
        repository=repo, 
        cloud=cloud, 
        llm=llm, 
        notifier=notifier
    )

# --- Routes WebSocket (Real-time Progress) ---

@app.websocket("/ws/progress/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Permet au frontend d'écouter l'avancement d'un benchmark en direct."""
    await ws_manager.connect(websocket, session_id)
    try:
        while True:
            # On garde la connexion ouverte
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id)

# --- Routes API : Gestion des Datasets ---

@app.post("/datasets/register", tags=["Admin"])
async def register_dataset(
    name: str, 
    path: str, 
    service: DatasetService = Depends(get_dataset_service)
):
    """Analyse un SQLite/CSV et l'enregistre avec son schéma."""
    dataset = service.register_dataset(name, path)
    return {"status": "success", "dataset": dataset}

@app.get("/datasets", tags=["Admin"])
async def list_datasets(service: DatasetService = Depends(get_dataset_service)):
    return service.list_datasets()

# --- Routes API : Exécution des Benchmarks ---

@app.post("/benchmarks/run/{team_id}", tags=["Execution"])
async def run_evaluation(
    team_id: UUID, 
    model_name: str,
    categories: List[str],
    background_tasks: BackgroundTasks,
    service: BenchmarkService = Depends(get_benchmark_service)
):
    """
    Lance un benchmark. Retourne immédiatement un session_id.
    Le progrès est envoyé via WebSocket sur /ws/progress/{session_id}
    """
    # 1. On prépare la session et on récupère son ID
    # Note: Assure-toi que ton BenchmarkService a une méthode init_session
    session_id = service.init_session(team_id, model_name)
    
    # 2. Exécution asynchrone pour ne pas bloquer l'API
    background_tasks.add_task(
        service.run_full_benchmark, 
        team_id, 
        model_name, 
        categories
    )
    
    return {
        "session_id": session_id,
        "status": "running",
        "websocket_url": f"/ws/progress/{session_id}"
    }

@app.get("/leaderboard", tags=["Results"])
async def get_leaderboard(service: BenchmarkService = Depends(get_benchmark_service)):
    """Affiche le classement actuel basé sur les TaskResults."""
    return service.get_leaderboard()