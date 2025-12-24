from fastapi import APIRouter, Depends
from uuid import UUID
from typing import List
from api.deps import get_team_service
from domain.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.post("/")
def create_team(
    name: str,
    hackathon_id: UUID,
    service: TeamService = Depends(get_team_service)
):
    return service.create_team(name, hackathon_id)


@router.get("/hackathon/{hackathon_id}")
def list_teams(
    hackathon_id: UUID,
    service: TeamService = Depends(get_team_service)
):
    return service.list_teams(hackathon_id)


@router.get("/{team_id}")
def get_team(
    team_id: UUID,
    service: TeamService = Depends(get_team_service)
):
    return service.get_team(team_id)


@router.delete("/{team_id}")
def delete_team(
    team_id: UUID,
    service: TeamService = Depends(get_team_service)
):
    service.delete_team(team_id)
    return {"status": "deleted"}
