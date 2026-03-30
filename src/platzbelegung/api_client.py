"""Client für die fussball.de REST API (iste2/Fu-ball.de-REST-API)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

from platzbelegung.models import Game, Team, TeamSide

logger = logging.getLogger(__name__)

_DATE_FMT = "%d.%m.%Y"


class ApiError(Exception):
    """Wird geworfen, wenn ein API-Aufruf fehlschlägt."""


class FussballDeApiClient:
    """HTTP-Client für die fussball.de REST API."""

    def __init__(self, base_url: str = "http://localhost:5000") -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Öffentliche Methoden
    # ------------------------------------------------------------------

    def get_teams(self, club_id: str, season: str) -> list[Team]:
        """Gibt alle Mannschaften eines Vereins zurück."""
        url = f"{self.base_url}/teams/club/{club_id}/season/{season}"
        data = self._get(url)
        return [self._parse_team(item) for item in data]

    def get_club_games(
        self,
        club_id: str,
        start: date,
        end: date,
        home_only: bool = False,
    ) -> list[Game]:
        """Gibt alle Spiele eines Vereins im angegebenen Zeitraum zurück."""
        url = f"{self.base_url}/games/club/{club_id}"
        params: dict[str, Any] = {
            "start": start.strftime(_DATE_FMT),
            "end": end.strftime(_DATE_FMT),
            "homeGamesOnly": str(home_only).lower(),
        }
        data = self._get(url, params=params)
        return [self._parse_game(item) for item in data]

    def get_team_games(
        self,
        team_id: str,
        start: date,
        end: date,
    ) -> list[Game]:
        """Gibt alle Spiele einer Mannschaft im angegebenen Zeitraum zurück."""
        url = f"{self.base_url}/games/team/{team_id}"
        params = {
            "start": start.strftime(_DATE_FMT),
            "end": end.strftime(_DATE_FMT),
        }
        data = self._get(url, params=params)
        return [self._parse_game(item) for item in data]

    def get_game_duration(self, team_kind: str) -> int:
        """Gibt die Spieldauer in Minuten für eine Mannschaftsart zurück."""
        url = f"{self.base_url}/gamesduration/teamkind/{team_kind}"
        data = self._get(url)
        # API gibt entweder eine Zahl oder {"duration": <int>} zurück
        if isinstance(data, (int, float)):
            return int(data)
        if isinstance(data, dict):
            return int(data.get("duration", 90))
        return 90

    # ------------------------------------------------------------------
    # Interne Hilfsmethoden
    # ------------------------------------------------------------------

    def _get(self, url: str, params: dict | None = None) -> Any:
        logger.debug("GET %s  params=%s", url, params)
        try:
            response = self._session.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"API-Aufruf fehlgeschlagen: {url} → {exc}") from exc
        return response.json()

    @staticmethod
    def _parse_team(data: dict) -> Team:
        return Team(
            id=data.get("id", ""),
            name=data.get("name", ""),
            link=data.get("link", ""),
            kind=data.get("kind", ""),
        )

    @staticmethod
    def _parse_team_side(data: dict) -> TeamSide:
        return TeamSide(
            id=data.get("id", ""),
            club_id=data.get("clubId", ""),
            name=data.get("name", ""),
            kind=data.get("kind", ""),
            link=data.get("link", ""),
            logo_url=data.get("logoUrl", ""),
        )

    def _parse_game(self, data: dict) -> Game:
        from datetime import datetime as dt

        kick_off_raw = data.get("kickOff", "")
        try:
            kick_off = dt.fromisoformat(kick_off_raw)
        except (ValueError, TypeError):
            kick_off = dt.min

        return Game(
            id=data.get("id", ""),
            kick_off=kick_off,
            home_side=self._parse_team_side(data.get("homeSide", {})),
            away_side=self._parse_team_side(data.get("awaySide", {})),
            league=data.get("league", ""),
            squad=data.get("squad", ""),
            squad_id=data.get("squadId", ""),
            address=data.get("address", ""),
            dfbnet_id=data.get("dfbnetId", ""),
            goals_home=data.get("goalsHome"),
            goals_away=data.get("goalsAway"),
            goals_home_half=data.get("goalsHomeHalf"),
            goals_away_half=data.get("goalsAwayHalf"),
            link=data.get("link", ""),
        )
