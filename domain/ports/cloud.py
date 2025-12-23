from abc import ABC, abstractmethod

class CloudProviderPort(ABC):
    @abstractmethod
    def provision_instance(self, docker_image: str) -> str:
        """Démarre un conteneur et retourne son ID ou son IP."""
        pass

    @abstractmethod
    def terminate_instance(self, instance_id: str) -> None:
        """Arrête et supprime l'instance pour ne pas gaspiller de crédits."""
        pass

    @abstractmethod
    def is_healthy(self, instance_id: str) -> bool:
        """Vérifie si le service sur la VM est prêt à recevoir du code."""
        pass