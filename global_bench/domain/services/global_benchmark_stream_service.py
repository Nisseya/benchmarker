from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict

from domain.ports.worker_selector import WorkerSelectorPort
from domain.ports.benchmark_repository import BenchmarkRepositoryPort
from domain.services.benchmark_enrichment_service import BenchmarkEnrichmentService
from infrastructure.sse.sse_client import aiter_sse_events


def sse(event: str, data: Dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@dataclass(frozen=True)
class GlobalStreamDeps:
    worker_selector: WorkerSelectorPort
    repo: BenchmarkRepositoryPort
    enrich: BenchmarkEnrichmentService


class GlobalBenchmarkStreamService:
    def __init__(self, deps: GlobalStreamDeps):
        self.deps = deps

    async def stream(
        self,
        model_id: str,
        revision: str,
        db_id: str,
        params: Dict[str, Any],
        request,
    ) -> AsyncGenerator[bytes, None]:
        run_id = uuid.uuid4()

        worker_base = await self.deps.worker_selector.select_worker_url()
        worker_url = f"{worker_base}/bench/complete/stream"

        await asyncio.to_thread(
            self.deps.repo.create_run,
            run_id,
            model_id,
            revision,
            db_id,
            params,
        )

        meta = {
            "run_id": str(run_id),
            "worker_url": worker_url,
            "model_id": model_id,
            "revision": revision,
            "db_id": db_id,
            **params,
        }

        await asyncio.to_thread(self.deps.repo.log_event, run_id, "meta", meta)
        yield sse("meta", meta)

        worker_payload = {
            "model": model_id,
            "revision": revision,
            "db_id": db_id,
            **params,
        }

        final_status = "ok"
        try:
            async for ev in aiter_sse_events(worker_url, worker_payload):
                if await request.is_disconnected():
                    final_status = "client_disconnected"
                    break

                if ev.event == "status":
                    payload = {**ev.data, "run_id": str(run_id)}
                    await asyncio.to_thread(self.deps.repo.log_event, run_id, "status", payload)
                    yield sse("status", payload)
                    continue

                if ev.event == "result":
                    base = {**ev.data, "run_id": str(run_id)}
                    pred_sql = base.get("sql")
                    gold_sql = base.get("gold_sql")
                    item_db_id = base.get("db_id") or db_id

                    if isinstance(pred_sql, str) and isinstance(gold_sql, str) and isinstance(item_db_id, str):
                        score = await asyncio.to_thread(self.deps.enrich.score_sqlite, item_db_id, pred_sql, gold_sql)
                        base["scoring"] = {
                            "pred_exec_success": score.pred_exec_success,
                            "gold_exec_success": score.gold_exec_success,
                            "is_correct": score.is_correct,
                            "pred_error": score.pred_error,
                            "gold_error": score.gold_error,
                            "rows_pred": score.rows_pred,
                            "rows_gold": score.rows_gold,
                            "match_kind": score.match_kind,
                            "pred_exec_time_ms": score.pred_exec_time_ms,
                            "gold_exec_time_ms": score.gold_exec_time_ms,
                            "scoring_time_ms": score.scoring_time_ms,
                        }

                    await asyncio.to_thread(self.deps.repo.log_event, run_id, "result", base)
                    await asyncio.to_thread(self.deps.repo.insert_item, run_id, base)
                    yield sse("result", base)
                    continue

                if ev.event == "done":
                    done_payload = {**ev.data, "run_id": str(run_id)}
                    await asyncio.to_thread(self.deps.repo.log_event, run_id, "done", done_payload)
                    yield sse("done", done_payload)
                    break

                passthrough = {**ev.data, "run_id": str(run_id)}
                await asyncio.to_thread(self.deps.repo.log_event, run_id, ev.event, passthrough)
                yield sse(ev.event, passthrough)

        except Exception as e:
            final_status = "error"
            err = {"run_id": str(run_id), "error": f"{type(e).__name__}: {e}"}
            await asyncio.to_thread(self.deps.repo.log_event, run_id, "error", err)
            yield sse("error", err)

        finally:
            await asyncio.to_thread(self.deps.repo.end_run, run_id, final_status)
