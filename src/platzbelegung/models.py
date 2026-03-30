"""Datenmodelle für die Platzbelegungs-Übersicht."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


@dataclass
class Team:
    """Eine Mannschaft eines Vereins."""

    id: str
    name: str
    link: str
    kind: str = ""  # Mannschaftsart, z.B. "Herren", "A-Junioren"


@dataclass
class TeamSide:
    """Eine Mannschaft als Heim- oder Auswärtsteam eines Spiels."""

    id: str
    club_id: str
    name: str
    kind: str
    link: str = ""
    logo_url: str = ""


@dataclass
class Game:
    """Ein Fußballspiel."""

    id: str
    kick_off: datetime
    home_side: TeamSide
    away_side: TeamSide
    league: str
    squad: str
    address: str
    squad_id: str = ""
    dfbnet_id: str = ""
    goals_home: Optional[str] = None
    goals_away: Optional[str] = None
    goals_home_half: Optional[str] = None
    goals_away_half: Optional[str] = None
    link: str = ""


@dataclass(frozen=True)
class Venue:
    """Eine Sportstätte (Spielort)."""

    name: str
    address: str

    def __str__(self) -> str:
        if self.name and self.name != self.address:
            return f"{self.name}, {self.address}"
        return self.address


@dataclass
class OccupancySlot:
    """Ein Belegungsslot: ein Heimspiel auf einer Sportstätte."""

    venue: Venue
    date: date
    start_time: time
    end_time: time
    team_name: str
    team_kind: str
    opponent: str
    league: str
    is_home_game: bool = True
