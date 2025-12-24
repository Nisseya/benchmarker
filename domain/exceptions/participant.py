from uuid import UUID


class ParticipantError(Exception):
    """Base class for participant-related domain errors."""


class ParticipantNotFound(ParticipantError):
    def __init__(self, participant_id: UUID | None = None):
        msg = "Participant not found"
        if participant_id:
            msg += f" (id={participant_id})"
        super().__init__(msg)


class ParticipantAlreadyExists(ParticipantError):
    def __init__(self, email: str):
        super().__init__(f"Participant with email '{email}' already exists")
