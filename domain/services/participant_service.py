from uuid import UUID, uuid4
from typing import List

from domain.models.identity import Participant
from domain.ports.repository import RepositoryPort
from domain.exceptions.participant import ParticipantNotFound


class ParticipantService:
    def __init__(self, repository: RepositoryPort):
        self.repository = repository

    def create_participant(
        self,
        first_name: str,
        last_name: str,
        email: str
    ) -> Participant:
        participant = Participant(
            id=uuid4(),
            first_name=first_name,
            last_name=last_name,
            email=email
        )
        self.repository.save_participant(participant)
        return participant

    def list_participants(self) -> List[Participant]:
        return self.repository.get_all_participants()

    def get_participant(self, participant_id: UUID) -> Participant:
        participant = self.repository.get_participant_by_id(participant_id)
        if participant is None:
            raise ParticipantNotFound(participant_id)
        return participant

    def delete_participant(self, participant_id: UUID):
        self.repository.delete_participant(participant_id)
