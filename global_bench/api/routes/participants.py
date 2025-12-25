from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from api.deps import get_participant_service
from domain.services.participant_service import ParticipantService

router = APIRouter(prefix="/participants", tags=["participants"])


class ParticipantCreateIn(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr


@router.post("/", status_code=201)
def create_participant(
    payload: ParticipantCreateIn,
    service: ParticipantService = Depends(get_participant_service),
):
    return service.create_participant(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
    )


@router.get("/")
def list_participants(service: ParticipantService = Depends(get_participant_service)):
    return service.list_participants()


@router.get("/{participant_id}")
def get_participant(
    participant_id: UUID,
    service: ParticipantService = Depends(get_participant_service),
):
    return service.get_participant(participant_id)


@router.delete("/{participant_id}", status_code=204)
def delete_participant(
    participant_id: UUID,
    service: ParticipantService = Depends(get_participant_service),
):
    service.delete_participant(participant_id)
    return None
