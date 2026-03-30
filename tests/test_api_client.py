"""Tests für den FussballDeApiClient."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from platzbelegung.api_client import ApiError, FussballDeApiClient
from platzbelegung.models import Game, Team


TEAM_RESPONSE = [
    {
        "id": "TEAM001",
        "name": "SKV Hochberg – Herren",
        "link": "https://www.fussball.de/mannschaft/...",
        "kind": "Herren",
    },
    {
        "id": "TEAM002",
        "name": "SKV Hochberg – A-Junioren",
        "link": "https://www.fussball.de/mannschaft/...",
        "kind": "A-Junioren",
    },
]

GAME_RESPONSE = [
    {
        "id": "GAME001",
        "kickOff": "2026-03-15T15:00:00",
        "homeSide": {
            "id": "SIDE001",
            "clubId": "CLUB001",
            "name": "SKV Hochberg",
            "kind": "Herren",
            "link": "",
            "logoUrl": "",
        },
        "awaySide": {
            "id": "SIDE002",
            "clubId": "CLUB002",
            "name": "FC Gegner",
            "kind": "Herren",
            "link": "",
            "logoUrl": "",
        },
        "league": "Kreisliga A",
        "squad": "Herren",
        "address": "Kunstrasenplatz, Sportanlage Hochberg, Hauptstr. 1, 70000 Stuttgart",
        "goalsHome": "3",
        "goalsAway": "1",
    }
]


def _mock_response(data) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


class TestGetTeams:
    def test_returns_team_list(self):
        client = FussballDeApiClient()
        with patch.object(client._session, "get", return_value=_mock_response(TEAM_RESPONSE)):
            teams = client.get_teams("CLUB001", "2526")

        assert len(teams) == 2
        assert isinstance(teams[0], Team)
        assert teams[0].id == "TEAM001"
        assert teams[0].name == "SKV Hochberg – Herren"
        assert teams[0].kind == "Herren"

    def test_raises_on_http_error(self):
        import requests

        client = FussballDeApiClient()
        mock = MagicMock()
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        with patch.object(client._session, "get", return_value=mock):
            with pytest.raises(ApiError):
                client.get_teams("CLUB001", "2526")


class TestGetClubGames:
    def test_returns_game_list(self):
        client = FussballDeApiClient()
        with patch.object(client._session, "get", return_value=_mock_response(GAME_RESPONSE)):
            games = client.get_club_games(
                "CLUB001",
                date(2026, 3, 1),
                date(2026, 3, 31),
            )

        assert len(games) == 1
        game = games[0]
        assert isinstance(game, Game)
        assert game.id == "GAME001"
        assert game.home_side.club_id == "CLUB001"
        assert game.away_side.name == "FC Gegner"
        assert game.league == "Kreisliga A"

    def test_kick_off_parsed(self):
        from datetime import datetime

        client = FussballDeApiClient()
        with patch.object(client._session, "get", return_value=_mock_response(GAME_RESPONSE)):
            games = client.get_club_games("CLUB001", date(2026, 3, 1), date(2026, 3, 31))

        assert games[0].kick_off == datetime(2026, 3, 15, 15, 0, 0)

    def test_passes_home_only_param(self):
        client = FussballDeApiClient()
        mock_get = MagicMock(return_value=_mock_response([]))
        with patch.object(client._session, "get", mock_get):
            client.get_club_games("CLUB001", date(2026, 3, 1), date(2026, 3, 31), home_only=True)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["homeGamesOnly"] == "true"


class TestGetGameDuration:
    def test_returns_int_from_number(self):
        client = FussballDeApiClient()
        with patch.object(client._session, "get", return_value=_mock_response(90)):
            duration = client.get_game_duration("Herren")
        assert duration == 90

    def test_returns_int_from_dict(self):
        client = FussballDeApiClient()
        with patch.object(client._session, "get", return_value=_mock_response({"duration": 70})):
            duration = client.get_game_duration("A-Junioren")
        assert duration == 70

    def test_fallback_on_unknown_format(self):
        client = FussballDeApiClient()
        with patch.object(client._session, "get", return_value=_mock_response({})):
            duration = client.get_game_duration("Unbekannt")
        assert duration == 90
