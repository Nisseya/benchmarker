from fastapi import APIRouter, Query
from app.core.config import settings
from app.services.model_store import ModelStore
from huggingface_hub import HfApi

router = APIRouter(prefix="/worker")

store = ModelStore(settings=settings, api=HfApi())

@router.get("/model_present")
def model_present(
    model_id: str = Query(...),
    revision: str = Query("main"),
):
    return {
        "model_id": model_id,
        "revision": revision,
        "present": store.is_on_nvme(model_id, revision),
    }


@router.get("/models")
def list_models():
    """
    Liste tous les modèles prêts (.READY) sur ce worker
    """
    models = store.list_ready_models()
    return {
        "count": len(models),
        "models": models,
    }