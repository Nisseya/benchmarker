import runpod
import httpx
import time
import logging
from typing import Dict, Any
from domain.ports.cloud import CloudProviderPort

class RunPodAdapter(CloudProviderPort):
    def __init__(self, api_key: str, worker_image: str):
        runpod.api_key = api_key
        self.worker_image = worker_image
        self.logger = logging.getLogger(__name__)

    def provision_instance(self, gpu_type: str = "NVIDIA GeForce RTX 3090") -> Dict[str, Any]:
        """Lance un pod et attend qu'il soit 'READY'."""
        self.logger.info(f"Provisioning RunPod instance with image {self.worker_image}...")
        
        pod = runpod.create_pod(
            name="benchmark-worker",
            image_name=self.worker_image,
            gpu_type_id=gpu_type,
            cloud_type="COMMUNITY",
            docker_args="/usr/bin/python3 -m worker.main", # Commande de lancement
            ports="8000/http" # Le port exposé par notre futur Docker
        )
        
        pod_id = pod["id"]
        return self._wait_for_ready(pod_id)

    def _wait_for_ready(self, pod_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Boucle de vérification pour obtenir l'IP du pod dès qu'il est actif."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            pod_status = runpod.get_pod(pod_id)
            if pod_status.get("runtime") and pod_status["runtime"]["status"] == "running":
                address = pod_status["runtime"]["address"]
                # On construit l'URL du endpoint exposé par le worker Docker
                return {
                    "pod_id": pod_id,
                    "url": f"http://{address}:8000"
                }
            time.sleep(5)
        raise TimeoutError(f"Pod {pod_id} failed to start in time.")

    async def send_task_to_worker(self, worker_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Envoie le code à exécuter au worker distant via HTTP."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{worker_url}/execute",
                json=payload,
                timeout=60.0
            )
            return response.json()

    def terminate_instance(self, pod_id: str):
        """Détruit le pod pour arrêter la facturation immédiatement."""
        runpod.terminate_pod(pod_id)
        self.logger.info(f"Pod {pod_id} terminated.")