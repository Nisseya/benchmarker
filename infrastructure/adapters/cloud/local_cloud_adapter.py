import docker
import time
import httpx
from typing import Dict, Any
from domain.ports.cloud import CloudProviderPort

class LocalCloudAdapter(CloudProviderPort):
    def __init__(self, image_name: str = "benchmark-worker-local"):
        self.client = docker.from_env()
        self.image_name = image_name
        self.container = None

    async def provision_instance(self) -> Dict[str, Any]:
        """Lance un conteneur Docker local au lieu d'un Pod RunPod."""
        print(f"DEBUG: Démarrage d'un conteneur local ({self.image_name})...")
        
        # On lance le worker sur le port 8001 pour ne pas entrer en conflit avec le backend
        self.container = self.client.containers.run(
            self.image_name,
            detach=True,
            ports={'8000/tcp': 8001}, 
            remove=True # Supprime le conteneur à l'arrêt
        )
        
        # On laisse un peu de temps au serveur interne pour démarrer
        time.sleep(2) 
        
        return {
            "pod_id": self.container.id,
            "url": "http://localhost:8001"
        }

    async def send_task_to_worker(self, worker_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Identique à l'adaptateur RunPod, mais sur localhost."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{worker_url}/execute",
                    json=payload,
                    timeout=30.0
                )
                return response.json()
            except Exception as e:
                return {"status": "error", "error": str(e)}

    def terminate_instance(self, pod_id: str):
        """Arrête le conteneur local."""
        if self.container:
            self.container.stop()
            print(f"DEBUG: Conteneur {pod_id[:12]} arrêté.")
            
    async def is_healthy(self, worker_url: str) -> bool:
        """
        Vérifie si le worker dans le conteneur est prêt à recevoir des requêtes.
        """
        async with httpx.AsyncClient() as client:
            try:
                # On tente d'appeler l'URL racine ou un endpoint de santé
                response = await client.get(f"{worker_url}/", timeout=1.0)
                return response.status_code == 200
            except (httpx.RequestError, httpx.HTTPStatusError):
                return False