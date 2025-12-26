from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from huggingface_hub import HfApi

from app.core.config import settings
from app.api.routes import bench_router, health_router, bench_tot_router, models_router
from app.services.model_store import ModelStore
from app.services.gpu_runtime import GpuRuntime
from app.services.benchmark import BenchRunner
from app.services.queue import JobQueue
from app.domain.models import BenchJob

def create_app() -> FastAPI:
    app = FastAPI(title="hf-benchmark-sse", version="1.0.0")

    app.include_router(health_router, tags=["health"])
    app.include_router(bench_router, tags=["bench"])
    app.include_router(bench_tot_router, tags=["complete benchmark"])
    app.include_router(models_router, tags=["Models"])

    @app.on_event("startup")
    async def startup():
        os.makedirs(settings.hf_cache_dir, exist_ok=True)
        os.makedirs(settings.model_store_dir, exist_ok=True)

        api = HfApi()
        store = ModelStore(settings=settings, api=api)
        runtime = GpuRuntime(settings=settings)
        runner = BenchRunner(settings=settings)
        
        app.state.model_store = store
        app.state.gpu_runtime = runtime
        app.state.bench_runner = runner

        q: asyncio.Queue[BenchJob] = asyncio.Queue(maxsize=settings.queue_maxsize)
        jq = JobQueue(settings=settings, store=store, runtime=runtime, runner=runner, queue=q)
        await jq.start_worker()

        app.state.job_queue = jq

    return app

app = create_app()
