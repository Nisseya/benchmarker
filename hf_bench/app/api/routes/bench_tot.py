from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.db import get_conn
from app.domain.sse import sse
from app.services.hf_resolver import parse_hf_input
from app.services.spider_service import SpiderService
from app.domain.spider.models import SchemaTextOptions
from app.services.model_store import ModelStore
from app.services.gpu_runtime import GpuRuntime
from app.domain.models import ModelSpec
from app.services.benchmark import BenchRunner

router = APIRouter()


class CompleteBenchmarkRequest(BaseModel):
    model: str = Field(..., description="HF repo id 'org/model' or https://huggingface.co/org/model")
    revision: Optional[str] = Field(None, description="HF revision (commit SHA recommended).")

    source_file: Optional[str] = Field(None, description="Filter spider_benchmark_questions.source_file")
    db_id: Optional[str] = Field(None, description="Filter spider_benchmark_questions.db_id")
    limit: int = Field(200, ge=1, le=100000)
    offset: int = Field(0, ge=0)

    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    do_sample: bool = False
    dtype: str = settings.dtype


def _get_store(request: Request) -> ModelStore:
    store = request.app.state.model_store
    if store is None:
        raise HTTPException(status_code=500, detail="Model store not initialized")
    return store


def _get_runtime(request: Request) -> GpuRuntime:
    rt = request.app.state.gpu_runtime
    if rt is None:
        raise HTTPException(status_code=500, detail="GPU runtime not initialized")
    return rt


def _get_runner(request: Request) -> BenchRunner:
    runner = request.app.state.bench_runner
    if runner is None:
        raise HTTPException(status_code=500, detail="Bench runner not initialized")
    return runner


@router.post("/bench/complete/stream")
async def complete_benchmark_stream(req: CompleteBenchmarkRequest, request: Request):
    model_id, revision = parse_hf_input(req.model, req.revision)

    if settings.require_revision and not revision:
        raise HTTPException(status_code=400, detail="revision is required (set REQUIRE_REVISION=0 to allow default).")
    revision = revision or "main"

    store = _get_store(request)
    runtime = _get_runtime(request)
    runner = _get_runner(request)

    async def stream() -> AsyncGenerator[bytes, None]:
        # --- phase: start
        yield sse("status", {"phase": "started", "model_id": model_id, "revision": revision}).encode("utf-8")

        # --- ensure model on disk (thread)
        yield sse("status", {"phase": "downloading_or_cache_check"}).encode("utf-8")
        t0 = time.perf_counter()
        local_path = await asyncio.to_thread(store.ensure_on_nvme, model_id, revision)
        yield sse("status", {"phase": "model_ready_on_nvme", "ms": (time.perf_counter() - t0) * 1000}).encode("utf-8")

        # --- load to GPU (thread)
        yield sse("status", {"phase": "loading_model_to_gpu"}).encode("utf-8")
        t1 = time.perf_counter()
        await asyncio.to_thread(runtime.ensure_loaded, ModelSpec(model_id, revision, req.dtype), local_path)
        yield sse("status", {"phase": "model_loaded", "ms": (time.perf_counter() - t1) * 1000, "gpu": runtime.gpu_stats()}).encode("utf-8")

        # --- pull questions (sqlite)
        yield sse("status", {"phase": "loading_questions"}).encode("utf-8")
        with get_conn() as conn:
            spider = SpiderService(
                conn=conn,
                schema_options=SchemaTextOptions(
                    use_original_names=True,
                    include_types=False,
                    max_columns_per_table=60,
                    max_total_chars=settings.max_prompt_chars,
                ),
            )
            items = spider.list_questions_with_schema(
                source_file=req.source_file,
                db_id=req.db_id,
                limit=req.limit,
                offset=req.offset,
            )

        yield sse("status", {"phase": "running", "count": len(items)}).encode("utf-8")

        # --- warmup once (use first question)
        if items:
            first = items[0]
            await asyncio.to_thread(
                runner.warmup,
                tokenizer=runtime.tokenizer,
                model=runtime.model,
                schema=first.schema_text,
                question=first.question.question,
            )
            yield sse("status", {"phase": "warmup_done"}).encode("utf-8")

        # --- run questions sequentially (stream each result)
        for i, item in enumerate(items):
            if await request.is_disconnected():
                break

            q = item.question
            schema = item.schema_text

            res = await asyncio.to_thread(
                runner.run_once,
                question_id=q.id,
                tokenizer=runtime.tokenizer,
                model=runtime.model,
                schema=schema,
                question=q.question,
                max_new_tokens=req.max_new_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
                do_sample=req.do_sample,
                gpu_stats_fn=runtime.gpu_stats,
            )

            payload = {
                "index": i,
                "question_id": res["question_id"],
                "db_id": q.db_id,
                "source_file": q.source_file,
                "source_index": q.source_index,
                "raw_answer": res["raw_answer"],
                "gen_time_ms": res["metrics"]["gen_time_ms"],
                "metrics": res["metrics"],
                # optionnel: utile pour debug / scoring
                "sql": res["sql"],
                "gold_sql": q.gold_sql,
            }
            yield sse("result", payload).encode("utf-8")

        yield sse("done", {"status": "ok"}).encode("utf-8")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
