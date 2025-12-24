from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from domain.services.hackathon_service import HackathonService
from domain.exceptions.hackathon import HackathonNotFound, HackathonAlreadyExists, HackathonInvalidDates
from api.deps import get_hackathon_service  # <-- add this

router = APIRouter(prefix="/hackathons", tags=["hackathons"])

class HackathonCreateIn(BaseModel):
    name: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class HackathonOut(BaseModel):
    id: UUID
    name: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    created_at: datetime

@router.post("/", response_model=HackathonOut, status_code=201)
def create_hackathon(
    payload: HackathonCreateIn,
    service: HackathonService = Depends(get_hackathon_service),
):
    try:
        h = service.create_hackathon(payload.name, payload.start_date, payload.end_date)
        return HackathonOut(**h.__dict__)
    except HackathonInvalidDates as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HackathonAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/", response_model=List[HackathonOut])
def list_hackathons(service: HackathonService = Depends(get_hackathon_service)):
    hs = service.list_hackathons()
    return [HackathonOut(**h.__dict__) for h in hs]

@router.get("/{hackathon_id}", response_model=HackathonOut)
def get_hackathon(hackathon_id: UUID, service: HackathonService = Depends(get_hackathon_service)):
    try:
        h = service.get_hackathon(hackathon_id)
        return HackathonOut(**h.__dict__)
    except HackathonNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{hackathon_id}", status_code=204)
def delete_hackathon(hackathon_id: UUID, service: HackathonService = Depends(get_hackathon_service)):
    try:
        service.delete_hackathon(hackathon_id)
    except HackathonNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
