from __future__ import annotations

import json
import uuid
from typing import Any, Dict

import psycopg2

from domain.ports.benchmark_repository import BenchmarkRepositoryPort


class BenchmarkRepositoryPG(BenchmarkRepositoryPort):
    def __init__(self, dsn: str):
        self.dsn = dsn

    def create_run(self, run_id: uuid.UUID, model_id: str, revision: str, db_id: str, params: Dict[str, Any]) -> None:
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bench_runs(run_id, model_id, revision, db_id, params, status)
                    VALUES (%s,%s,%s,%s,%s::jsonb,'running')
                    """,
                    (str(run_id), model_id, revision, db_id, json.dumps(params)),
                )

    def end_run(self, run_id: uuid.UUID, status: str) -> None:
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE bench_runs SET ended_at = NOW(), status = %s WHERE run_id = %s",
                    (status, str(run_id)),
                )

    def log_event(self, run_id: uuid.UUID, event_type: str, payload: Dict[str, Any]) -> None:
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO bench_events(run_id, event_type, payload) VALUES (%s,%s,%s::jsonb)",
                    (str(run_id), event_type, json.dumps(payload)),
                )

    def insert_item(self, run_id: uuid.UUID, item: Dict[str, Any]) -> None:
        scoring = item.get("scoring") or {}
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bench_items(
                      run_id, idx, question_id, db_id, source_index,
                      raw_answer, sql, gold_sql, gen_time_ms, metrics,
                      pred_exec_success, gold_exec_success, is_correct,
                      pred_error, gold_error, rows_pred, rows_gold, match_kind
                    )
                    VALUES (
                      %s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s::jsonb,
                      %s,%s,%s,
                      %s,%s,%s,%s,%s
                    )
                    """,
                    (
                        str(run_id),
                        item.get("index"),
                        item.get("question_id"),
                        item.get("db_id"),
                        item.get("source_index"),
                        item.get("raw_answer"),
                        item.get("sql"),
                        item.get("gold_sql"),
                        item.get("gen_time_ms"),
                        json.dumps(item.get("metrics") or {}),
                        scoring.get("pred_exec_success"),
                        scoring.get("gold_exec_success"),
                        scoring.get("is_correct"),
                        scoring.get("pred_error"),
                        scoring.get("gold_error"),
                        scoring.get("rows_pred"),
                        scoring.get("rows_gold"),
                        scoring.get("match_kind"),
                    ),
                )
