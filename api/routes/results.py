from fastapi import APIRouter, Depends

from domain.services.benchmark_service import BenchmarkService
from api.deps import get_benchmark_service

router = APIRouter(tags=["Results"])


@router.get("/leaderboard")
async def get_leaderboard(service: BenchmarkService = Depends(get_benchmark_service)):
    return service.get_leaderboard()
