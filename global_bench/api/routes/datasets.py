from fastapi import APIRouter, Depends

from domain.services.dataset_service import DatasetService
from api.deps import get_dataset_service

router = APIRouter(prefix="/datasets", tags=["Admin"])


@router.post("/register")
async def register_dataset(
    name: str,
    path: str,
    service: DatasetService = Depends(get_dataset_service),
):
    dataset = service.register_dataset(name, path)
    return {"status": "success", "dataset": dataset}


@router.get("")
async def list_datasets(service: DatasetService = Depends(get_dataset_service)):
    return service.list_datasets()
