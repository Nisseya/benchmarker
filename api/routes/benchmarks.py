from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, BackgroundTasks

from domain.services.benchmark_service import BenchmarkService
from api.deps import get_benchmark_service

router = APIRouter(prefix="/benchmarks", tags=["Execution"])


@router.post("/run/{team_id}")
async def run_evaluation(
    team_id: UUID,
    model_name: str,
    categories: List[str],
    background_tasks: BackgroundTasks,
    service: BenchmarkService = Depends(get_benchmark_service),
):
    session_id = service.init_session(team_id, model_name)

    background_tasks.add_task(
        service.run_full_benchmark,
        team_id,
        model_name,
        categories,
    )

    return {
        "session_id": session_id,
        "status": "running",
        "websocket_url": f"/ws/progress/{session_id}",
    }
