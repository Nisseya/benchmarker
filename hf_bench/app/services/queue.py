from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import HTTPException

from app.domain.models import BenchJob, ModelSpec
from app.domain.sse import sse
from app.core.config import Settings
from app.services.model_store import ModelStore
from app.services.gpu_runtime import GpuRuntime
from app.services.benchmark import BenchRunner

@dataclass
class JobQueue:
    settings: Settings
    store: ModelStore
    runtime: GpuRuntime
    runner: BenchRunner
    queue: asyncio.Queue[BenchJob]

    async def emit(self, job: BenchJob, event: str, payload: dict) -> None:
        await job.events.put(sse(event, payload))

    async def start_worker(self) -> None:
        async def loop():
            while True:
                job = await self.queue.get()
                try:
                    await self.emit(job, "status", {"phase": "started", "job_id": job.job_id})

                    await self.emit(job, "status", {"phase": "downloading_or_cache_check"})
                    t0 = time.perf_counter()
                    local_path = self.store.ensure_on_nvme(job.model_id, job.revision)
                    await self.emit(job, "status", {"phase": "model_ready_on_nvme", "ms": (time.perf_counter()-t0)*1000})

                    await self.emit(job, "status", {"phase": "loading_model_to_gpu"})
                    t1 = time.perf_counter()
                    self.runtime.ensure_loaded(ModelSpec(job.model_id, job.revision, job.dtype), local_path)
                    await self.emit(job, "status", {"phase": "model_loaded", "ms": (time.perf_counter()-t1)*1000, "gpu": self.runtime.gpu_stats()})

                    await self.emit(job, "status", {"phase": "running"})
                    result = self.runner.run_once(
                        tokenizer=self.runtime.tokenizer,
                        model=self.runtime.model,
                        schema=job.schema,
                        question=job.question,
                        max_new_tokens=job.max_new_tokens,
                        temperature=job.temperature,
                        top_p=job.top_p,
                        do_sample=job.do_sample,
                        gpu_stats_fn=self.runtime.gpu_stats,
                    )

                    await self.emit(job, "result", {
                        "status": "success",
                        "model_id": job.model_id,
                        "revision": job.revision,
                        "device": self.settings.device,
                        "dtype": job.dtype,
                        **result,
                    })
                    await self.emit(job, "done", {"job_id": job.job_id})

                except HTTPException as he:
                    await self.emit(job, "error", {"job_id": job.job_id, "detail": he.detail, "status_code": he.status_code})
                    await self.emit(job, "done", {"job_id": job.job_id})
                except Exception as e:
                    await self.emit(job, "error", {"job_id": job.job_id, "detail": repr(e)})
                    await self.emit(job, "done", {"job_id": job.job_id})
                finally:
                    self.queue.task_done()

        asyncio.create_task(loop())

    def enqueue(self, job: BenchJob) -> None:
        try:
            self.queue.put_nowait(job)
        except asyncio.QueueFull:
            raise HTTPException(status_code=429, detail="Server queue is full. Try again later.")
