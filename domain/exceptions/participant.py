from uuid import UUID
from domain.exceptions.base import DomainError

class ParticipantNotFound(DomainError):
    def __init__(self, participant_id: UUID | None = None):
        msg = "Participant not found"
        if participant_id:
            msg += f" (id={participant_id})"
        super().__init__(msg)


class ParticipantAlreadyExists(DomainError):
    def __init__(self, email: str):
        super().__init__(f"Participant with email '{email}' already exists")
