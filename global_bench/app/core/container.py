from __future__ import annotations

from app.core.settings import Settings
from domain.services.execution_service import ExecutionService
from domain.services.benchmark_enrichment_service import BenchmarkEnrichmentService
from domain.services.global_benchmark_stream_service import GlobalBenchmarkStreamService, GlobalStreamDeps

from infrastructure.workers.local_worker_selector import LocalWorkerSelector
from infrastructure.adapters.repository.benchmark_repository_pg import BenchmarkRepositoryPG


class Container:
    def __init__(self, settings: Settings):
        self.settings = settings

        self.worker_selector = LocalWorkerSelector(settings.worker_base_url)

        self.exec_service = ExecutionService(datasets_root=settings.datasets_root)
        self.enrich_service = BenchmarkEnrichmentService(self.exec_service)

        self.repo = BenchmarkRepositoryPG(settings.pg_dsn)

        self.global_stream = GlobalBenchmarkStreamService(
            GlobalStreamDeps(
                worker_selector=self.worker_selector,
                repo=self.repo,
                enrich=self.enrich_service,
            )
        )
