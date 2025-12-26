from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from domain.services.execution_service import ExecutionService


@dataclass(frozen=True)
class ScoredResult:
    pred_exec_success: bool
    gold_exec_success: bool
    is_correct: Optional[bool]
    pred_error: Optional[str]
    gold_error: Optional[str]
    rows_pred: Optional[int]
    rows_gold: Optional[int]
    match_kind: str
    pred_exec_time_ms: Optional[float]
    gold_exec_time_ms: Optional[float]
    scoring_time_ms: float


class BenchmarkEnrichmentService:
    def __init__(self, exec_service: ExecutionService):
        self.exec_service = exec_service

    def _normalize_rows(self, rows: Any) -> list[tuple[str, ...]]:
        if rows is None:
            return []
        out: list[tuple[str, ...]] = []
        for r in rows:
            out.append(tuple("NULL" if x is None else str(x) for x in r))
        return out

    def score_sqlite(self, db_id: str, pred_sql: str, gold_sql: str) -> ScoredResult:
        t0 = time.perf_counter()

        pred = self.exec_service.execute("sqlite", db_id=db_id, code=pred_sql, context={}).result
        gold = self.exec_service.execute("sqlite", db_id=db_id, code=gold_sql, context={}).result

        scoring_ms = (time.perf_counter() - t0) * 1000.0

        pred_time = float(pred.execution_time_ms) if pred.execution_time_ms is not None else None
        gold_time = float(gold.execution_time_ms) if gold.execution_time_ms is not None else None

        if not pred.success or not gold.success:
            return ScoredResult(
                pred_exec_success=bool(pred.success),
                gold_exec_success=bool(gold.success),
                is_correct=None,
                pred_error=pred.error,
                gold_error=gold.error,
                rows_pred=None,
                rows_gold=None,
                match_kind="exec_failed",
                pred_exec_time_ms=pred_time,
                gold_exec_time_ms=gold_time,
                scoring_time_ms=scoring_ms,
            )

        pred_rows = pred.output or []
        gold_rows = gold.output or []

        p = sorted(self._normalize_rows(pred_rows))
        g = sorted(self._normalize_rows(gold_rows))

        ok = p == g

        return ScoredResult(
            pred_exec_success=True,
            gold_exec_success=True,
            is_correct=ok,
            pred_error=None,
            gold_error=None,
            rows_pred=len(pred_rows),
            rows_gold=len(gold_rows),
            match_kind="sorted_string_rows",
            pred_exec_time_ms=pred_time,
            gold_exec_time_ms=gold_time,
            scoring_time_ms=scoring_ms,
        )
