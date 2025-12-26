# domain/services/execution_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from domain.ports.executor import ExecutionResult
from infrastructure.executor import DatasetLocator, make_executor, ExecutorKind


@dataclass(frozen=True)
class ExecutionRequest:
    executor_kind: ExecutorKind
    db_id: str
    code: str
    context: Dict[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionResponse:
    executor_kind: ExecutorKind
    db_id: str
    result: ExecutionResult


class ExecutionService:
    def __init__(self, datasets_root: str):
        self.locator = DatasetLocator(datasets_root)

    def execute(
        self,
        executor_kind: ExecutorKind,
        db_id: str,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResponse:
        ctx = dict(context or {})

        executor = make_executor(executor_kind, self.locator)
        res = executor.execute(code=code, db_id=db_id, context=ctx)

        return ExecutionResponse(
            executor_kind=executor_kind,
            db_id=db_id,
            result=res,
        )

    def execute_request(self, req: ExecutionRequest) -> ExecutionResponse:
        return self.execute(
            executor_kind=req.executor_kind,
            db_id=req.db_id,
            code=req.code,
            context=req.context,
        )
