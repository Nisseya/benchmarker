from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.core.container import Container
from app.core.deps import get_container


router = APIRouter()


def parse_hf_input(model: str, revision: Optional[str]) -> tuple[str, str]:
    m = model.strip()
    if m.startswith("https://huggingface.co/"):
        m = m.replace("https://huggingface.co/", "", 1).strip("/")
    rev = (revision or "main").strip()
    return m, rev


class CompleteBenchmarkRequest(BaseModel):
    model: str = Field(...)
    revision: Optional[str] = None

    db_id: str = Field(...)

    limit: int = Field(200, ge=1, le=100000)
    offset: int = Field(0, ge=0)

    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    do_sample: bool = False
    dtype: str = "auto"


@router.post("/bench/complete/stream")
async def complete_benchmark_stream(
    req: CompleteBenchmarkRequest,
    request: Request,
    container: Container = Depends(get_container),
):
    model_id, revision = parse_hf_input(req.model, req.revision)

    params = {
        "db_id": req.db_id,
        "limit": req.limit,
        "offset": req.offset,
        "max_new_tokens": req.max_new_tokens,
        "temperature": req.temperature,
        "top_p": req.top_p,
        "do_sample": req.do_sample,
        "dtype": req.dtype,
    }

    async def stream():
        async for chunk in container.global_stream.stream(
            model_id=model_id,
            revision=revision,
            db_id=req.db_id,
            params={k: v for k, v in params.items() if k != "db_id"},
            request=request,
        ):
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
