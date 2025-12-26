from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from domain.services.execution_service import ExecutionService
from domain.services.benchmark_enrichment_service import BenchmarkEnrichmentService
from domain.services.global_benchmark_stream_service import GlobalBenchmarkStreamService, GlobalStreamDeps
from infrastructure.repository.benchmark_repository_pg import BenchmarkRepositoryPG
from infrastructure.workers.local_worker_selector import LocalWorkerSelector


router = APIRouter()


def parse_hf_input(model: str, revision: Optional[str]) -> tuple[str, str]:
    m = model.strip()
    if m.startswith("https://huggingface.co/"):
        m = m.replace("https://huggingface.co/", "", 1).strip("/")
    rev = (revision or "main").strip()
    return m, rev


class CompleteBenchmarkRequest(BaseModel):
    model: str = Field(..., description="HF repo id 'org/model' or https://huggingface.co/org/model")
    revision: Optional[str] = Field(None, description="HF revision (commit SHA recommended).")

    db_id: str = Field(..., description="Dataset id (Spider db_id).")
    limit: int = Field(200, ge=1, le=100000)
    offset: int = Field(0, ge=0)

    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    do_sample: bool = False
    dtype: str = "auto"


@router.post("/bench/complete/stream")
async def complete_benchmark_stream(req: CompleteBenchmarkRequest, request: Request):
    model_id, revision = parse_hf_input(req.model, req.revision)

    worker_selector = LocalWorkerSelector("http://localhost:8001")

    exec_service = ExecutionService(datasets_root="datasets/test_database")
    enrich = BenchmarkEnrichmentService(exec_service)

    repo = BenchmarkRepositoryPG(dsn="postgresql://postgres:postgres@localhost:5432/postgres")

    svc = GlobalBenchmarkStreamService(
        GlobalStreamDeps(worker_selector=worker_selector, repo=repo, enrich=enrich)
    )

    params = {
        "limit": req.limit,
        "offset": req.offset,
        "max_new_tokens": req.max_new_tokens,
        "temperature": req.temperature,
        "top_p": req.top_p,
        "do_sample": req.do_sample,
        "dtype": req.dtype,
    }

    async def stream():
        async for chunk in svc.stream(
            model_id=model_id,
            revision=revision,
            db_id=req.db_id,
            params=params,
            request=request,
        ):
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
