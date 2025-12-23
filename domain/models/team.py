from dataclasses import dataclass

@dataclass(frozen=True)
class Team:
    team_id: str
    name: str
    api_key: str