"""Datenmodelle für die Platzbelegungs-Übersicht."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


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
    """Ein Belegungsslot: ein Heimspiel oder Training auf einer Sportstätte."""

    venue: Venue
    date: date
    start_time: time
    end_time: time
    team_name: str
    team_kind: str
    opponent: str
    league: str
    is_home_game: bool = True
    is_training: bool = False
    source_url: str = ""


@dataclass
class TrainingSession:
    """Eine wiederkehrende Trainingseinheit, gescraped von einer Vereins-Webseite.

    Eine ``TrainingSession`` ist nicht an ein konkretes Datum gebunden, sondern
    gibt den Wochentag und die Uhrzeit des Trainings an.  Sie wird mit
    :func:`platzbelegung.parser.training_sessions_to_occupancy` in konkrete
    :class:`OccupancySlot`-Objekte für einen Zeitraum umgewandelt.
    """

    club_name: str
    team_name: str
    weekday: int            # 0=Montag, 6=Sonntag
    start_time: time
    end_time: Optional[time]
    venue_name: str
    source_url: str
    scraped_at: str = ""
    duration_minutes: int = 90

    def to_dict(self) -> dict:
        """Serialisiert die Trainingseinheit in ein dict (JSON-kompatibel)."""
        return {
            "clubName": self.club_name,
            "teamName": self.team_name,
            "weekday": self.weekday,
            "startTime": self.start_time.strftime("%H:%M"),
            "endTime": self.end_time.strftime("%H:%M") if self.end_time else None,
            "venueName": self.venue_name,
            "sourceUrl": self.source_url,
            "scrapedAt": self.scraped_at,
            "durationMinutes": self.duration_minutes,
        }

    @classmethod
    def from_dict(cls, data: dict, scraped_at: str = "") -> "TrainingSession":
        """Erstellt ein TrainingSession-Objekt aus einem dict."""
        start_raw = data.get("startTime", "")
        end_raw = data.get("endTime")
        try:
            start = time.fromisoformat(start_raw) if start_raw else time(0, 0)
        except ValueError:
            start = time(0, 0)
        end: Optional[time] = None
        if end_raw:
            try:
                end = time.fromisoformat(end_raw)
            except ValueError:
                end = None
        return cls(
            club_name=data.get("clubName", ""),
            team_name=data.get("teamName", ""),
            weekday=int(data.get("weekday", 0)),
            start_time=start,
            end_time=end,
            venue_name=data.get("venueName", ""),
            source_url=data.get("sourceUrl", ""),
            scraped_at=data.get("scrapedAt", scraped_at),
            duration_minutes=int(data.get("durationMinutes", 90)),
        )
