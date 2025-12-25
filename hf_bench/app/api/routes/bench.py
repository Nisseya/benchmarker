from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.models import BenchJob
from app.domain.sse import sse
from app.services.hf_resolver import parse_hf_input

router = APIRouter()

class BenchRequest(BaseModel):
    model: str = Field(..., description="HF repo id 'org/model' or https://huggingface.co/org/model")
    revision: Optional[str] = Field(None, description="HF revision (commit SHA recommended).")
    schema: str
    question: str
    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    do_sample: bool = False
    dtype: str = settings.dtype

def get_job_queue(request: Request):
    jq = request.app.state.job_queue
    if jq is None:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    return jq

@router.post("/bench/stream")
async def bench_stream(req: BenchRequest, request: Request):
    model_id, revision = parse_hf_input(req.model, req.revision)

    if settings.require_revision and not revision:
        raise HTTPException(status_code=400, detail="revision is required (set REQUIRE_REVISION=0 to allow default).")
    revision = revision or "main"

    job = BenchJob(
        job_id=str(uuid.uuid4()),
        model_id=model_id,
        revision=revision,
        schema=req.schema,
        question=req.question,
        max_new_tokens=req.max_new_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
        do_sample=req.do_sample,
        dtype=req.dtype,  # type: ignore
    )

    jq = get_job_queue(request)
    jq.enqueue(job)

    async def stream() -> AsyncGenerator[bytes, None]:
        yield sse("status", {"phase": "queued", "job_id": job.job_id, "queue_size": jq.queue.qsize()}).encode("utf-8")
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await job.events.get()
                yield msg.encode("utf-8")
                if msg.startswith("event: done"):
                    break
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
