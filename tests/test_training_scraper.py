"""Tests für den ClubWebsiteScraper (training_scraper.py) und training_sessions_to_occupancy."""

from __future__ import annotations

from datetime import date, time
from unittest.mock import MagicMock, patch

import pytest

from platzbelegung.config import ClubConfig
from platzbelegung.models import TrainingSession
from platzbelegung.training_scraper import (
    ClubWebsiteScraper,
    _compute_duration,
    _parse_time,
    _parse_time_range,
    _parse_weekday,
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
# Hilfsfunktion-Tests
# ---------------------------------------------------------------------------


class TestParseTime:
    def test_hhmm_colon(self):
        assert _parse_time("18:00") == time(18, 0)

    def test_hhmm_dot(self):
        assert _parse_time("18.30") == time(18, 30)

    def test_embedded_in_text(self):
        assert _parse_time("Training um 19:30 Uhr") == time(19, 30)

    def test_no_time_returns_none(self):
        assert _parse_time("kein Zeitstempel") is None


class TestParseTimeRange:
    def test_single_time(self):
        start, end = _parse_time_range("18:00")
        assert start == time(18, 0)
        assert end is None

    def test_range_dash(self):
        start, end = _parse_time_range("18:00 - 20:00")
        assert start == time(18, 0)
        assert end == time(20, 0)

    def test_range_en_dash(self):
        start, end = _parse_time_range("18:00 – 20:00")
        assert start == time(18, 0)
        assert end == time(20, 0)

    def test_no_time(self):
        start, end = _parse_time_range("kein Zeitstempel")
        assert start is None
        assert end is None


class TestParseWeekday:
    def test_montag(self):
        assert _parse_weekday("Montag") == 0

    def test_mo_abbreviation(self):
        assert _parse_weekday("Mo.") == 0

    def test_freitag(self):
        assert _parse_weekday("Freitag 18:00") == 4

    def test_sonntag(self):
        assert _parse_weekday("Sonntag") == 6

    def test_no_weekday_returns_none(self):
        assert _parse_weekday("Training um 18:00") is None

    def test_case_insensitive(self):
        assert _parse_weekday("MONTAG") == 0


class TestComputeDuration:
    def test_with_end_time(self):
        assert _compute_duration(time(18, 0), time(20, 0)) == 120

    def test_without_end_time(self):
        assert _compute_duration(time(18, 0), None) == 90

    def test_negative_diff_returns_default(self):
        # end before start – edge case
        assert _compute_duration(time(20, 0), time(18, 0)) == 90


# ---------------------------------------------------------------------------
# ClubWebsiteScraper – Tabellen
# ---------------------------------------------------------------------------

_TABLE_HTML = """
<html><body>
  <h1>Trainingszeiten SGV Hochdorf</h1>
  <table>
    <thead>
      <tr><th>Mannschaft</th><th>Tag</th><th>Uhrzeit</th></tr>
    </thead>
    <tbody>
      <tr><td>Herren</td><td>Dienstag</td><td>18:30 - 20:00</td></tr>
      <tr><td>B-Junioren</td><td>Donnerstag</td><td>17:00 - 18:30</td></tr>
    </tbody>
  </table>
</body></html>
"""


class TestClubWebsiteScraperTables:
    def test_parses_table_rows(self):
        scraper = ClubWebsiteScraper()
        club_cfg = ClubConfig(
            name="SGV Hochdorf",
            training_url="https://example.com/training",
            venue_name="Sportplatz Hochdorf",
        )
        with patch.object(
            scraper._session, "get", return_value=_mock_response(_TABLE_HTML)
        ):
            sessions = scraper.scrape_club(club_cfg)

        assert len(sessions) == 2
        assert sessions[0].weekday == 1  # Dienstag
        assert sessions[0].start_time == time(18, 30)
        assert sessions[0].end_time == time(20, 0)
        assert sessions[0].team_name == "Herren"
        assert sessions[0].club_name == "SGV Hochdorf"
        assert sessions[0].source_url == "https://example.com/training"

        assert sessions[1].weekday == 3  # Donnerstag
        assert sessions[1].start_time == time(17, 0)
        assert sessions[1].end_time == time(18, 30)
        assert sessions[1].team_name == "B-Junioren"

    def test_scrape_no_url_returns_empty(self):
        scraper = ClubWebsiteScraper()
        club_cfg = ClubConfig(name="Kein URL", training_url="", venue_name="")
        sessions = scraper.scrape_club(club_cfg)
        assert sessions == []

    def test_network_error_returns_empty(self):
        import requests as _requests

        scraper = ClubWebsiteScraper()
        club_cfg = ClubConfig(
            name="Fehler-Club",
            training_url="https://example.com/training",
            venue_name="",
        )
        with patch.object(
            scraper._session,
            "get",
            side_effect=_requests.exceptions.ConnectionError("fail"),
        ):
            sessions = scraper.scrape_club(club_cfg)
        assert sessions == []


# ---------------------------------------------------------------------------
# ClubWebsiteScraper – Listen
# ---------------------------------------------------------------------------

_LIST_HTML = """
<html><body>
  <h2>Trainingszeiten</h2>
  <h3>Herren</h3>
  <ul>
    <li>Montag 19:00 - 20:30 Uhr</li>
    <li>Mittwoch 19:00 - 20:30 Uhr</li>
  </ul>
  <h3>A-Junioren</h3>
  <ul>
    <li>Freitag 17:00 - 18:30 Uhr</li>
  </ul>
</body></html>
"""


class TestClubWebsiteScraperLists:
    def test_parses_list_items(self):
        scraper = ClubWebsiteScraper()
        club_cfg = ClubConfig(
            name="VfB Neckarrems",
            training_url="https://example.com/training",
            venue_name="Sportplatz",
        )
        with patch.object(
            scraper._session, "get", return_value=_mock_response(_LIST_HTML)
        ):
            sessions = scraper.scrape_club(club_cfg)

        assert len(sessions) >= 2
        weekdays = {s.weekday for s in sessions}
        assert 0 in weekdays  # Montag
        assert 2 in weekdays  # Mittwoch


# ---------------------------------------------------------------------------
# ClubWebsiteScraper – Duplikat-Entfernung
# ---------------------------------------------------------------------------

_DUPLICATE_HTML = """
<html><body>
  <table>
    <tr><td>Herren</td><td>Montag</td><td>18:00 - 20:00</td></tr>
    <tr><td>Herren</td><td>Montag</td><td>18:00 - 20:00</td></tr>
  </table>
</body></html>
"""


class TestDeduplication:
    def test_duplicates_are_removed(self):
        scraper = ClubWebsiteScraper()
        club_cfg = ClubConfig(
            name="Test", training_url="https://example.com", venue_name=""
        )
        with patch.object(
            scraper._session, "get", return_value=_mock_response(_DUPLICATE_HTML)
        ):
            sessions = scraper.scrape_club(club_cfg)
        # Duplikate sollen entfernt werden
        assert len(sessions) <= 1


# ---------------------------------------------------------------------------
# TrainingSession – Serialisierung
# ---------------------------------------------------------------------------


class TestTrainingSessionSerialization:
    def test_to_dict_and_back(self):
        ts = TrainingSession(
            club_name="SKV Hochberg",
            team_name="Herren",
            weekday=1,
            start_time=time(19, 0),
            end_time=time(20, 30),
            venue_name="Sportplatz",
            source_url="https://example.com",
            scraped_at="2026-04-10T00:00:00Z",
            duration_minutes=90,
        )
        d = ts.to_dict()
        restored = TrainingSession.from_dict(d, "2026-04-10T00:00:00Z")
        assert restored.club_name == ts.club_name
        assert restored.team_name == ts.team_name
        assert restored.weekday == ts.weekday
        assert restored.start_time == ts.start_time
        assert restored.end_time == ts.end_time
        assert restored.source_url == ts.source_url

    def test_from_dict_without_end_time(self):
        d = {
            "clubName": "SKV",
            "teamName": "Damen",
            "weekday": 2,
            "startTime": "18:00",
            "endTime": None,
            "venueName": "Halle",
            "sourceUrl": "https://example.com",
            "durationMinutes": 90,
        }
        ts = TrainingSession.from_dict(d)
        assert ts.end_time is None
        assert ts.start_time == time(18, 0)


# ---------------------------------------------------------------------------
# training_sessions_to_occupancy
# ---------------------------------------------------------------------------


class TestTrainingSessionsToOccupancy:
    def test_expands_to_correct_dates(self):
        from platzbelegung.parser import training_sessions_to_occupancy

        # Dienstag = 1
        session = TrainingSession(
            club_name="SKV",
            team_name="Herren",
            weekday=1,
            start_time=time(19, 0),
            end_time=time(20, 30),
            venue_name="Sportplatz",
            source_url="https://example.com",
        )
        # 2026-04-13 is a Monday, 2026-04-14 is a Tuesday
        slots = training_sessions_to_occupancy(
            [session],
            date_start=date(2026, 4, 13),
            date_end=date(2026, 4, 19),
        )
        assert len(slots) == 1
        assert slots[0].date == date(2026, 4, 14)  # Dienstag
        assert slots[0].start_time == time(19, 0)
        assert slots[0].end_time == time(20, 30)
        assert slots[0].is_training is True
        assert slots[0].source_url == "https://example.com"

    def test_multiple_weeks(self):
        from platzbelegung.parser import training_sessions_to_occupancy

        session = TrainingSession(
            club_name="SKV",
            team_name="Herren",
            weekday=0,  # Montag
            start_time=time(18, 0),
            end_time=time(20, 0),
            venue_name="Platz",
            source_url="",
        )
        # 3 Wochen: sollte 3 Montage ergeben
        slots = training_sessions_to_occupancy(
            [session],
            date_start=date(2026, 4, 6),   # Montag
            date_end=date(2026, 4, 26),
        )
        assert len(slots) == 3

    def test_end_time_computed_from_duration(self):
        from platzbelegung.parser import training_sessions_to_occupancy

        session = TrainingSession(
            club_name="SKV",
            team_name="Herren",
            weekday=2,  # Mittwoch
            start_time=time(18, 0),
            end_time=None,
            venue_name="Platz",
            source_url="",
            duration_minutes=90,
        )
        slots = training_sessions_to_occupancy(
            [session],
            date_start=date(2026, 4, 15),  # Mittwoch
            date_end=date(2026, 4, 15),
        )
        assert len(slots) == 1
        assert slots[0].end_time == time(19, 30)

    def test_is_training_flag_set(self):
        from platzbelegung.parser import training_sessions_to_occupancy

        session = TrainingSession(
            club_name="SKV",
            team_name="Herren",
            weekday=0,
            start_time=time(19, 0),
            end_time=time(20, 30),
            venue_name="Platz",
            source_url="https://example.com",
        )
        slots = training_sessions_to_occupancy(
            [session],
            date_start=date(2026, 4, 6),
            date_end=date(2026, 4, 6),
        )
        assert len(slots) == 1
        assert slots[0].is_training is True
        assert slots[0].source_url == "https://example.com"

    def test_empty_sessions_returns_empty_list(self):
        from platzbelegung.parser import training_sessions_to_occupancy

        slots = training_sessions_to_occupancy(
            [],
            date_start=date(2026, 4, 1),
            date_end=date(2026, 4, 30),
        )
        assert slots == []

    def test_results_sorted_by_date_and_time(self):
        from platzbelegung.parser import training_sessions_to_occupancy

        sessions = [
            TrainingSession(
                club_name="SKV", team_name="Herren", weekday=4,  # Freitag
                start_time=time(19, 0), end_time=time(20, 30),
                venue_name="Platz", source_url="",
            ),
            TrainingSession(
                club_name="SKV", team_name="Junioren", weekday=1,  # Dienstag
                start_time=time(17, 0), end_time=time(18, 30),
                venue_name="Platz", source_url="",
            ),
        ]
        # Woche vom 13.04 (Mo) bis 19.04 (So)
        slots = training_sessions_to_occupancy(
            sessions,
            date_start=date(2026, 4, 13),
            date_end=date(2026, 4, 19),
        )
        assert len(slots) == 2
        assert slots[0].date < slots[1].date  # Dienstag vor Freitag
