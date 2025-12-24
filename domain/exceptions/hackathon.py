from __future__ import annotations
from uuid import UUID
from domain.exceptions.base import DomainError

class HackathonNotFound(DomainError):
    def __init__(self, hackathon_id: UUID):
        super().__init__(f"Hackathon not found (id={hackathon_id})")

class HackathonAlreadyExists(DomainError):
    def __init__(self, name: str):
        super().__init__(f"Hackathon already exists (name='{name}')")

class HackathonInvalidDates(DomainError):
    def __init__(self):
        super().__init__("Invalid dates: start_date must be <= end_date")
