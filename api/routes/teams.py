from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from api.deps import get_team_service
from domain.services.team_service import TeamService
from domain.models.identity import Participant
from domain.exceptions import TeamNotFound, ParticipantNotFound

router = APIRouter(prefix="/teams", tags=["teams"])

class TeamCreateIn(BaseModel):
    name: str
    hackathon_id: UUID

@router.post("/", status_code=201)
def create_team(
    payload: TeamCreateIn,
    service: TeamService = Depends(get_team_service),
):
    return service.create_team(
        name=payload.name,
        hackathon_id=payload.hackathon_id,
    )

@router.get("/hackathon/{hackathon_id}")
def list_teams_by_hackathon(
    hackathon_id: UUID,
    service:TeamService = Depends(get_team_service),
):
    return service.list_teams(hackathon_id)

@router.get("/{team_id}")
def get_team(
    team_id: UUID,
    service:TeamService = Depends(get_team_service),
):
    return service.get_team(team_id)

@router.delete("/{team_id}", status_code=204)
def delete_team(
    team_id: UUID,
    service: TeamService = Depends(get_team_service),
):
    service.delete_team(team_id)
    return None


class TeamAddParticipantIn(BaseModel):
    participant_id: UUID


@router.post("/{team_id}/participants", status_code=204)
def add_participant_to_team(
    team_id: UUID,
    payload: TeamAddParticipantIn,
    service: TeamService = Depends(get_team_service),
):
    service.add_participant_to_team(team_id, payload.participant_id)
    return None

@router.delete("/{team_id}/participants/{participant_id}", status_code=204)
def remove_participant_from_team(
    team_id: UUID,
    participant_id: UUID,
    service: TeamService = Depends(get_team_service),
):
    try:
        service.remove_participant_from_team(team_id, participant_id)
        return None
    except TeamNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ParticipantNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))