import runpod
import httpx
import time
import logging
import asyncio
from typing import Dict, Any
from domain.ports.cloud import CloudProviderPort

class RunPodAdapter(CloudProviderPort):
    def __init__(self, api_key: str, worker_image: str):
        runpod.api_key = api_key
        self.worker_image = worker_image
        self.logger = logging.getLogger(__name__)

    async def is_healthy(self, worker_url: str) -> bool:
        """
        Vérifie si le serveur FastAPI à l'intérieur du Pod RunPod répond.
        """
        async with httpx.AsyncClient() as client:
            try:
                # On interroge l'endpoint racine du worker
                response = await client.get(f"{worker_url}/", timeout=2.0)
                return response.status_code == 200
            except (httpx.RequestError, httpx.HTTPStatusError):
                return False

    async def provision_instance(self, gpu_type: str = "NVIDIA GeForce RTX 3090") -> Dict[str, Any]:
        """Lance un pod et attend qu'il soit 'READY' ET 'HEALTHY'."""
        self.logger.info(f"Provisioning RunPod instance with image {self.worker_image}...")
        
        pod = runpod.create_pod(
            name="benchmark-worker",
            image_name=self.worker_image,
            gpu_type_id=gpu_type,
            cloud_type="COMMUNITY",
            docker_args="python3 -m worker_api", # Assure-toi que c'est le bon point d'entrée
            ports="8000/http"
        )
        
        pod_id = pod["id"]
        # On attend que l'IP soit assignée et le service prêt
        return await self._wait_for_ready_and_healthy(pod_id)

    async def _wait_for_ready_and_healthy(self, pod_id: str, timeout: int = 600) -> Dict[str, Any]:
        """
        Combine la vérification du statut RunPod et le check de santé HTTP.
        """
        start_time = time.time()
        url = None

        while time.time() - start_time < timeout:
            pod_status = runpod.get_pod(pod_id)
            
            # 1. Vérifier si RunPod a fini de déployer le container
            if pod_status.get("runtime") and pod_status["runtime"]["status"] == "running":
                address = pod_status["runtime"]["address"]
                url = f"http://{address}:8000"
                
                # 2. Vérifier si notre application interne répond
                if await self.is_healthy(url):
                    self.logger.info(f"Pod {pod_id} is healthy and ready.")
                    return {"pod_id": pod_id, "url": url}
                
                self.logger.info(f"Pod {pod_id} is running, waiting for worker API...")
            
            # Pause asynchrone pour ne pas bloquer l'event loop
            await asyncio.sleep(5)
            
        raise TimeoutError(f"Pod {pod_id} failed to reach healthy state in time.")

    async def send_task_to_worker(self, worker_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Envoie le code à exécuter au worker distant via HTTP."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{worker_url}/execute",
                json=payload,
                timeout=90.0 # Plus long pour les tâches complexes
            )
            return response.json()

    def terminate_instance(self, pod_id: str):
        """Détruit le pod pour arrêter la facturation."""
        runpod.terminate_pod(pod_id)
        self.logger.info(f"Pod {pod_id} terminated.")