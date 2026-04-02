"""Tests für den FussballDeScraper (scraper.py)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from platzbelegung.scraper import (
    FussballDeScraper,
    _parse_german_datetime,
    filter_games_by_venues,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _mock_response(html: str) -> MagicMock:
    mock = MagicMock()
    mock.text = html
    mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# _parse_german_datetime
# ---------------------------------------------------------------------------

class TestParseGermanDatetime:
    def test_full_date_and_time(self):
        dt = _parse_german_datetime("28.03.2026", "14:00")
        assert dt == datetime(2026, 3, 28, 14, 0)

    def test_date_without_time(self):
        dt = _parse_german_datetime("01.01.2026", "")
        assert dt == datetime(2026, 1, 1, 0, 0)

    def test_invalid_date_returns_none(self):
        assert _parse_german_datetime("not-a-date", "12:00") is None

    def test_empty_string_returns_none(self):
        assert _parse_german_datetime("", "") is None


# ---------------------------------------------------------------------------
# FussballDeScraper – scrape_venue_games
# ---------------------------------------------------------------------------

_TABLE_HTML = """
<html><body>
  <h1 class="headline">Kunstrasenplatz</h1>
  <table class="table-striped">
    <tbody>
      <tr>
        <td>28.03.2026</td>
        <td>14:00</td>
        <td>SKV Hochberg</td>
        <td></td>
        <td>FC Muster</td>
        <td>Kreisliga A</td>
      </tr>
      <tr>
        <td>05.04.2026</td>
        <td>10:00</td>
        <td>SKV Hochberg II</td>
        <td></td>
        <td>SV Test</td>
        <td>Kreisliga B</td>
      </tr>
    </tbody>
  </table>
</body></html>
"""


class TestScrapeVenueGames:
    def test_parses_table_rows(self):
        scraper = FussballDeScraper()
        with patch.object(scraper._session, "get", return_value=_mock_response(_TABLE_HTML)):
            games = scraper.scrape_venue_games("VENUE001")

        assert len(games) == 2
        g = games[0]
        assert g.venue_id == "VENUE001"
        assert g.venue_name == "Kunstrasenplatz"
        assert g.date == "28.03.2026"
        assert g.time == "14:00"
        assert g.home_team == "SKV Hochberg"
        assert g.guest_team == "FC Muster"
        assert g.competition == "Kreisliga A"
        assert g.start_date == "2026-03-28T14:00:00"
        assert g.scraped_at  # non-empty timestamp

    def test_scraped_at_is_utc_iso(self):
        scraper = FussballDeScraper()
        with patch.object(scraper._session, "get", return_value=_mock_response(_TABLE_HTML)):
            games = scraper.scrape_venue_games("X")
        for game in games:
            assert "T" in game.scraped_at  # looks like ISO 8601

    def test_empty_page_returns_empty_list(self):
        html = "<html><body><h1 class='headline'>Leer</h1></body></html>"
        scraper = FussballDeScraper()
        with patch.object(scraper._session, "get", return_value=_mock_response(html)):
            games = scraper.scrape_venue_games("EMPTY")
        assert games == []


# ---------------------------------------------------------------------------
# FussballDeScraper – Fallback-Parser
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """
<html><body>
  <h2 class="headline">Rasenplatz</h2>
  <div class="fixture-list-item">
    <span class="date">12.04.2026</span>
    <span class="time">11:00</span>
    <span class="home-team">TSV Alpha</span>
    <span class="guest-team">VfB Beta</span>
    <span class="competition">B-Junioren</span>
  </div>
</body></html>
"""


class TestScrapeVenueGamesFallback:
    def test_parses_fixture_items(self):
        scraper = FussballDeScraper()
        with patch.object(scraper._session, "get", return_value=_mock_response(_FIXTURE_HTML)):
            games = scraper.scrape_venue_games("V2")

        assert len(games) == 1
        g = games[0]
        assert g.home_team == "TSV Alpha"
        assert g.guest_team == "VfB Beta"
        assert g.competition == "B-Junioren"
        assert g.venue_name == "Rasenplatz"


# ---------------------------------------------------------------------------
# ScrapedGame serialisation round-trip
# ---------------------------------------------------------------------------

class TestScrapedGameSerialization:
    def test_to_dict_and_back(self):
        from platzbelegung.models import ScrapedGame

        g = ScrapedGame(
            venue_id="V1",
            venue_name="Platz",
            date="01.04.2026",
            time="15:00",
            home_team="Home",
            guest_team="Away",
            competition="Kreisliga",
            start_date="2026-04-01T15:00:00",
            scraped_at="2026-03-30T10:00:00Z",
        )
        d = g.to_dict()
        g2 = ScrapedGame.from_dict(d)
        assert g2.venue_id == g.venue_id
        assert g2.home_team == g.home_team
        assert g2.start_date == g.start_date


# ---------------------------------------------------------------------------
# FussballDeScraper – scrape_club_matchplan (JSON)
# ---------------------------------------------------------------------------

_MATCHPLAN_JSON = {
    "matches": [
        {
            "venue": {"id": "VENUE001", "name": "Kunstrasenplatz"},
            "date": "28.03.2026",
            "time": "14:00",
            "homeTeam": {"name": "SKV Hochberg"},
            "awayTeam": {"name": "FC Muster"},
            "competition": {"name": "Kreisliga A"},
        },
        {
            "venue": {"id": "VENUE002", "name": "Rasenplatz"},
            "date": "05.04.2026",
            "time": "16:00",
            "homeTeam": {"name": "SKV Hochberg II"},
            "awayTeam": {"name": "SV Test"},
            "competition": {"name": "Kreisliga B"},
        },
    ]
}


class TestScrapeClubMatchplan:
    def test_parses_json_response(self):
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "application/json"}
        mock.json.return_value = _MATCHPLAN_JSON
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert len(games) == 2
        g = games[0]
        assert g.venue_id == "VENUE001"
        assert g.venue_name == "Kunstrasenplatz"
        assert g.date == "28.03.2026"
        assert g.time == "14:00"
        assert g.home_team == "SKV Hochberg"
        assert g.guest_team == "FC Muster"
        assert g.competition == "Kreisliga A"
        assert g.start_date == "2026-03-28T14:00:00"

    def test_parses_html_response(self):
        """Test HTML fragment parsing from ajax.club.matchplan."""
        html = """
        <div class="match-row" data-venue-id="V123">
            <span class="date">10.04.2026</span>
            <span class="time">15:30</span>
            <span class="home-team">Team A</span>
            <span class="guest-team">Team B</span>
            <span class="competition">Bezirksliga</span>
            <span class="venue-name">Sportplatz Nord</span>
        </div>
        """
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "text/html"}
        mock.text = html
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("CLUB002")

        assert len(games) == 1
        g = games[0]
        assert g.venue_id == "V123"
        assert g.home_team == "Team A"
        assert g.guest_team == "Team B"

    def test_pagination_stops_on_empty_response(self):
        """Test that pagination stops when no more games are returned."""
        scraper = FussballDeScraper()
        call_count = 0

        # Create a larger first page (20+ items) to trigger pagination
        large_match_list = {
            "matches": [
                {
                    "venue": {"id": f"V{i:03d}", "name": f"Venue {i}"},
                    "date": "01.04.2026",
                    "time": "10:00",
                    "homeTeam": {"name": f"Team Home {i}"},
                    "awayTeam": {"name": f"Team Away {i}"},
                    "competition": {"name": "Liga"},
                }
                for i in range(25)  # More than 20 to trigger pagination
            ]
        }

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            mock.headers = {"content-type": "application/json"}
            if call_count == 1:
                mock.json.return_value = large_match_list
            else:
                # Second call returns empty
                mock.json.return_value = {"matches": []}
            mock.raise_for_status.return_value = None
            return mock

        with patch.object(scraper._session, "get", side_effect=mock_get):
            games = scraper.scrape_club_matchplan("CLUB003", limit=100)

        # Should have fetched first page and tried second
        assert len(games) == 25
        assert call_count == 2  # Initial + one more attempt


# ---------------------------------------------------------------------------
# filter_games_by_venues
# ---------------------------------------------------------------------------


class TestFilterGamesByVenues:
    def test_filters_by_venue_ids(self):
        from platzbelegung.models import ScrapedGame

        games = [
            ScrapedGame(
                venue_id="V1", venue_name="P1", date="", time="",
                home_team="A", guest_team="B", competition="",
                start_date="2026-04-01T10:00:00", scraped_at="",
            ),
            ScrapedGame(
                venue_id="V2", venue_name="P2", date="", time="",
                home_team="C", guest_team="D", competition="",
                start_date="2026-04-01T12:00:00", scraped_at="",
            ),
            ScrapedGame(
                venue_id="V3", venue_name="P3", date="", time="",
                home_team="E", guest_team="F", competition="",
                start_date="2026-04-01T14:00:00", scraped_at="",
            ),
        ]

        filtered = filter_games_by_venues(games, ["V1", "V3"])
        assert len(filtered) == 2
        assert filtered[0].venue_id == "V1"
        assert filtered[1].venue_id == "V3"

    def test_returns_all_when_no_filter(self):
        from platzbelegung.models import ScrapedGame

        games = [
            ScrapedGame(
                venue_id="V1", venue_name="P1", date="", time="",
                home_team="A", guest_team="B", competition="",
                start_date="2026-04-01T10:00:00", scraped_at="",
            ),
        ]

        filtered = filter_games_by_venues(games, [])
        assert len(filtered) == 1

    def test_returns_empty_when_no_match(self):
        from platzbelegung.models import ScrapedGame

        games = [
            ScrapedGame(
                venue_id="V1", venue_name="P1", date="", time="",
                home_team="A", guest_team="B", competition="",
                start_date="2026-04-01T10:00:00", scraped_at="",
            ),
        ]

        filtered = filter_games_by_venues(games, ["V2", "V3"])
        assert len(filtered) == 0

