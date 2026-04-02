"""Datenmodelle für die Platzbelegungs-Übersicht."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time


@dataclass
class ScrapedGame:
    """Ein Spiel, das direkt von fussball.de gescraped wurde.

    Entspricht dem flachen JSON-Format, das im Snapshot gespeichert wird
    und vom Web-Server ausgeliefert wird.
    """

    venue_id: str
    venue_name: str
    date: str           # deutsches Format, z.B. "28.03.2026"
    time: str           # Uhrzeit, z.B. "14:00"
    home_team: str
    guest_team: str
    competition: str
    start_date: str     # ISO 8601, z.B. "2026-03-28T14:00:00"
    scraped_at: str     # ISO 8601 UTC, z.B. "2026-03-30T09:54:51Z"

    def to_dict(self) -> dict:
        """Serialisiert das Spiel in ein dict (JSON-kompatibel)."""
        return {
            "venueId": self.venue_id,
            "venueName": self.venue_name,
            "date": self.date,
            "time": self.time,
            "homeTeam": self.home_team,
            "guestTeam": self.guest_team,
            "competition": self.competition,
            "startDate": self.start_date,
            "scrapedAt": self.scraped_at,
        }

    @classmethod
    def from_dict(cls, data: dict, scraped_at: str = "") -> "ScrapedGame":
        """Erstellt ein ScrapedGame-Objekt aus einem dict."""
        return cls(
            venue_id=data.get("venueId", ""),
            venue_name=data.get("venueName", ""),
            date=data.get("date", ""),
            time=data.get("time", ""),
            home_team=data.get("homeTeam", ""),
            guest_team=data.get("guestTeam", ""),
            competition=data.get("competition", ""),
            start_date=data.get("startDate", ""),
            scraped_at=data.get("scrapedAt", scraped_at),
        )


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
