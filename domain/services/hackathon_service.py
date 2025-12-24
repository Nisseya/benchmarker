from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from domain.ports.repository import RepositoryPort
from domain.models.hackathon import Hackathon
from domain.exceptions.hackathon import (
    HackathonNotFound,
    HackathonAlreadyExists,
    HackathonInvalidDates,
)

class HackathonService:
    def __init__(self, repository: RepositoryPort):
        self.repo = repository

    def create_hackathon(
        self,
        name: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Hackathon:
        if start_date and end_date and start_date > end_date:
            raise HackathonInvalidDates()

        existing = self.repo.get_hackathon_by_name(name)
        if existing is not None:
            raise HackathonAlreadyExists(name)

        h = Hackathon(
            id=uuid.uuid4(),
            name=name,
            start_date=start_date,
            end_date=end_date,
            created_at=datetime.utcnow(),
        )
        self.repo.create_hackathon(h)
        return h

    def get_hackathon(self, hackathon_id: UUID) -> Hackathon:
        h = self.repo.get_hackathon_by_id(hackathon_id)
        if h is None:
            raise HackathonNotFound(hackathon_id)
        return h

    def list_hackathons(self) -> List[Hackathon]:
        return self.repo.list_hackathons()

    def delete_hackathon(self, hackathon_id: UUID) -> None:
        h = self.repo.get_hackathon_by_id(hackathon_id)
        if h is None:
            raise HackathonNotFound(hackathon_id)
        self.repo.delete_hackathon(hackathon_id)
