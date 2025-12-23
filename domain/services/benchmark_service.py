import uuid

from domain.models.benchmark import BenchmarkTask
from domain.models.evaluation import Evaluation
from domain.ports.executor import ExecutorPort
from domain.ports.cloud import CloudProviderPort
from domain.ports.repository import RepositoryPort
from domain.ports.llm import LLMClientPort

class BenchmarkService:
    def __init__(
        self,
        cloud_provider: CloudProviderPort,
        executor: ExecutorPort,
        llm_client: LLMClientPort,
        repository: RepositoryPort
    ):
        self.cloud_provider = cloud_provider
        self.executor = executor
        self.llm_client = llm_client
        self.repository = repository

    def run_full_benchmark(self, model_id: str, category: str):
        """Lance l'évaluation complète pour un modèle donné."""
        tasks = self.repository.get_all_tasks(category)
        
        # 1. On prépare l'infrastructure (ex: RunPod)
        # On peut réutiliser la même instance pour toute la série de tests
        instance_id = self.cloud_provider.provision_instance(docker_image="eval-runner:latest")
        
        try:
            for task in tasks:
                self._evaluate_single_task(model_id, instance_id, task)
        finally:
            # 2. On éteint toujours la machine pour éviter de vider le compte RunPod
            self.cloud_provider.terminate_instance(instance_id)

    def _evaluate_single_task(self, model_id: str, instance_id: str, task: BenchmarkTask):
        # 3. Génération du code par le LLM testé
        prompt = f"Question: {task.question}\nContext: {task.context_db_path}"
        generated_code = self.llm_client.generate_code(prompt, model_id)

        # 4. Exécution du code (via le port qui communique avec RunPod ou Docker)
        # On passe le contexte (ex: chemin de la DB SQLite de Spider)
        exec_result = self.executor.execute(generated_code, context={"db": task.context_db_path})

        # 5. Validation "Silver Standard"
        # On compare l'état des variables capturées avec le code Gold
        gold_exec = self.executor.execute(task.gold_answer_code, context={"db": task.context_db_path})
        
        silver_score = self._calculate_state_similarity(
            exec_result.captured_state, 
            gold_exec.captured_state
        )

        # 6. Validation "LLM-as-a-Judge" (Optionnel pour le SQL, crucial pour Python)
        judge_feedback = self.llm_client.judge_answer(
            question=task.question,
            code=generated_code,
            output=exec_result.output
        )

        # 7. Création de l'entité Evaluation et sauvegarde
        eval_run = Evaluation(
            evaluation_id=str(uuid.uuid4()),
            task_id=task.task_id,
            model_name=model_id,
            generated_code=generated_code,
            is_correct=(exec_result.output == gold_exec.output),
            silver_score=silver_score,
            judge_feedback=judge_feedback,
            metrics=exec_result.metrics # Contient temps, RAM, CPU
        )

        self.repository.save_result(eval_run)

    def _calculate_state_similarity(self, state_a: dict, state_b: dict) -> float:
        """Logique interne pour comparer les variables (Silver Standard)."""
        if not state_a or not state_b:
            return 0.0
        # Ici, on compare les clés et les valeurs des dictionnaires de variables
        common_keys = set(state_a.keys()) & set(state_b.keys())
        if not common_keys:
            return 0.0
        
        matches = sum(1 for k in common_keys if state_a[k] == state_b[k])
        return matches / max(len(state_a), len(state_b))