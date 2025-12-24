from fastapi import APIRouter, Depends
from uuid import UUID
from api.deps import get_participant_service
from domain.services.participant_service import ParticipantService

router = APIRouter(prefix="/participants", tags=["Participants"])


@router.post("/")
def create_participant(
    first_name: str,
    last_name: str,
    email: str,
    service: ParticipantService = Depends(get_participant_service)
):
    return service.create_participant(first_name, last_name, email)


@router.get("/")
def list_participants(
    service: ParticipantService = Depends(get_participant_service)
):
    return service.list_participants()


@router.get("/{participant_id}")
def get_participant(
    participant_id: UUID,
    service: ParticipantService = Depends(get_participant_service)
):
    return service.get_participant(participant_id)


@router.delete("/{participant_id}")
def delete_participant(
    participant_id: UUID,
    service: ParticipantService = Depends(get_participant_service)
):
    service.delete_participant(participant_id)
    return {"status": "deleted"}
