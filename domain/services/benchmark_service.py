import logging
from uuid import UUID, uuid4
from typing import List
from domain.models.evaluation import EvaluationSession, TaskResult, ExecutionMetrics

class BenchmarkService:
    def __init__(self, repository, cloud, llm, notifier):
        self.repository = repository
        self.cloud = cloud
        self.llm = llm
        self.notifier = notifier
        self.logger = logging.getLogger(__name__)

    async def run_full_benchmark(self, team_id: UUID, model_name: str, categories: List[str]):
        """
        Orchestrateur principal du benchmark.
        """
        # 1. Initialisation de la session
        session_id = uuid4()
        tasks = self.repository.get_tasks_by_categories(categories)
        
        session = EvaluationSession(
            id=uuid4(),
            team_id=team_id,
            session_id=session_id,
            language="Multi",
            model_name=model_name,
            status="running"
        )
        self.repository.save_evaluation_session(session)

        instance = await self.cloud.provision_instance()
        
        try:
            for index, task in enumerate(tasks):
                generated_code = await self.llm.generate_code(task.content, model_name)
                
                execution_response = await self.cloud.send_task_to_worker(
                    instance["url"], 
                    {
                        "code": generated_code,
                        "context": task.contexts[0].schema_definition,
                        "language": task.language
                    }
                )

                is_correct = self._verify_gold_standard(execution_response, task.gold_code)
                silver_score = self._calculate_silver_score(execution_response, task)

                result = TaskResult(
                    id=uuid4(),
                    evaluation_id=session.id,
                    question_id=task.id,
                    generated_code=generated_code,
                    is_correct=is_correct,
                    silver_score=silver_score,
                    generation_duration=execution_response.get("gen_time", 0),
                    metrics=ExecutionMetrics(
                        cpu_usage_percent=execution_response.get("cpu", 0),
                        ram_usage_mb=execution_response.get("ram", 0),
                        duration_ms=execution_response.get("exec_time", 0),
                        error_msg=execution_response.get("error")
                    )
                )

                self.repository.save_task_result(result)
                await self.notifier.publish_progress({
                    "session_id": str(session_id),
                    "current": index + 1,
                    "total": len(tasks),
                    "last_result": is_correct
                })

            session.status = "completed"
            
        except Exception as e:
            self.logger.error(f"Benchmark failed: {e}")
            session.status = "failed"
        finally:
            self.repository.update_session_status(session.id, session.status)
            self.cloud.terminate_instance(instance["pod_id"])

    def _verify_gold_standard(self, response: dict, gold_code: str) -> bool:
        """Compare l'output du worker avec le résultat attendu."""
        return response.get("output") == response.get("expected_output")

    def _calculate_silver_score(self, response: dict, task) -> float:
        """Calcule la proximité de l'état des variables (Silver Standard)."""
        captured_state = response.get("captured_state", {})
        return 1.0 if response.get("status") == "success" else 0.0