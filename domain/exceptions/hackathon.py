from __future__ import annotations
from uuid import UUID

class HackathonError(Exception):
    pass

class HackathonNotFound(HackathonError):
    def __init__(self, hackathon_id: UUID):
        super().__init__(f"Hackathon not found (id={hackathon_id})")

class HackathonAlreadyExists(HackathonError):
    def __init__(self, name: str):
        super().__init__(f"Hackathon already exists (name='{name}')")

class HackathonInvalidDates(HackathonError):
    def __init__(self):
        super().__init__("Invalid dates: start_date must be <= end_date")
