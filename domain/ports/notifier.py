from abc import ABC, abstractmethod

class NotifierPort(ABC):
    @abstractmethod
    async def publish_progress(self, data: dict):
        pass