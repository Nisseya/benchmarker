from uuid import UUID
from domain.exceptions.base import DomainError


class TeamNotFound(DomainError):
    def __init__(self, team_id: UUID):
        super().__init__(f"Team with id '{team_id}' not found")


class TeamAlreadyExists(DomainError):
    def __init__(self, name: str):
        super().__init__(f"Team with name '{name}' already exists")


class ParticipantNotInTeam(DomainError):
    def __init__(self, team_id: UUID, participant_id: UUID):
        super().__init__(
            f"Participant '{participant_id}' is not a member of team '{team_id}'"
        )
