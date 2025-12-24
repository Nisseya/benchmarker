from uuid import UUID, uuid4
from datetime import datetime
from typing import List

from domain.models.identity import Team, Participant


class TeamService:
    def __init__(self, repository):
        self.repository = repository

    def create_team(self, name: str, hackathon_id: UUID) -> Team:
        team = Team(
            id=uuid4(),
            name=name,
            hackathon_id=hackathon_id,
            created_at=datetime.utcnow(),
            members=[]
        )
        self.repository.save_team(team)
        return team

    def list_teams(self, hackathon_id: UUID) -> List[Team]:
        return self.repository.get_teams_by_hackathon(hackathon_id)

    def get_team(self, team_id: UUID) -> Team:
        return self.repository.get_team_by_id(team_id)

    def delete_team(self, team_id: UUID):
        self.repository.delete_team(team_id)

    def add_participant_to_team(self, team_id: UUID, participant: Participant):
        self.repository.add_participant_to_team(team_id, participant)
