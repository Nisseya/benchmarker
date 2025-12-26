import os

from fastapi import Depends
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from infrastructure.adapters.repository.postgres_repository import PostgresRepository
from infrastructure.adapters.cloud.runpod_adapter import RunPodAdapter
from infrastructure.adapters.cloud.local_cloud_adapter import LocalCloudAdapter
from infrastructure.adapters.llm.openai_adapter import OpenAIAdapter
from infrastructure.adapters.notifier.websocket_notifier import ConnectionManager, WebSocketNotifier

from domain.services.benchmark_service import BenchmarkService
from domain.services.dataset_service import DatasetService
from domain.services.team_service import TeamService
from domain.services.participant_service import ParticipantService
from domain.services.hackathon_service import HackathonService


ws_manager = ConnectionManager()


def get_repository(db: Session = Depends(get_db)) -> PostgresRepository:
    return PostgresRepository(db)


def get_cloud_adapter():
    env = os.getenv("APP_ENV", "local")
    if env == "production":
        return RunPodAdapter(
            api_key=os.getenv("RUNPOD_API_KEY", "none"),
            worker_image=os.getenv("WORKER_IMAGE_URL", "none"),
        )
    return LocalCloudAdapter(image_name="benchmark-worker-local")


def get_llm_adapter():
    return OpenAIAdapter(api_key=os.getenv("OPENAI_API_KEY", "none"))


def get_dataset_service(repo: PostgresRepository = Depends(get_repository)) -> DatasetService:
    return DatasetService(repository=repo)


def get_team_service(repo: PostgresRepository = Depends(get_repository)) -> TeamService:
    return TeamService(repository=repo)


def get_participant_service(repo: PostgresRepository = Depends(get_repository)) -> ParticipantService:
    return ParticipantService(repository=repo)

def get_hackathon_service(repo: PostgresRepository = Depends(get_repository)) -> HackathonService:
    return HackathonService(repository=repo)


def get_benchmark_service(
    repo: PostgresRepository = Depends(get_repository),
    cloud=Depends(get_cloud_adapter),
    llm=Depends(get_llm_adapter),
) -> BenchmarkService:
    notifier = WebSocketNotifier(ws_manager)
    return BenchmarkService(repository=repo, cloud=cloud, llm=llm, notifier=notifier)
