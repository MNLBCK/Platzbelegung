"""Tests für den FussballDeScraper (scraper.py)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from platzbelegung.scraper import (
    FussballDeScraper,
    _is_placeholder_team,
    _normalize_venue_name,
    _parse_german_datetime,
    filter_games_by_venue_configs,
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

_REAL_MATCHPLAN_HTML_WITHOUT_VENUES = """
<div data-ng-controller="AjaxController" id="id-club-matchplan-table" class="fixtures-matches">
  <div class="table-container fixtures-matches-table club-matchplan-table">
    <table class="table table-striped table-full-width">
      <tbody>
        <tr class="odd row-competition hidden-small">
          <td class="column-date"><span class="hidden-small inline">So, 12.04.26 |&nbsp;</span>15:00</td>
          <td colspan="3" class="column-team">
            <a>Herren | Kreisliga A; Kreisliga</a>
          </td>
          <td colspan="2">
            <a>ME | 355926184</a>
          </td>
        </tr>
        <tr class="odd">
          <td class="hidden-small"></td>
          <td class="column-club">
            <a class="club-wrapper">
              <div class="club-name">SGM Hochberg/&#8203;Hochdorf</div>
            </a>
          </td>
          <td class="column-colon">:</td>
          <td class="column-club no-border">
            <a class="club-wrapper">
              <div class="club-name">VfB Neckarrems 1913 e.V.</div>
            </a>
          </td>
          <td class="column-score"></td>
          <td class="column-detail"></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
"""

_REAL_MATCHPLAN_HTML_WITH_VENUES = """
<div data-ng-controller="AjaxController" id="id-club-matchplan-table" class="fixtures-matches">
  <div class="table-container fixtures-matches-table club-matchplan-table">
    <table class="table table-striped table-full-width">
      <tbody>
        <tr class="odd row-competition hidden-small">
          <td class="column-date"><span class="hidden-small inline">Sa, 11.04.26 |&nbsp;</span>12:00</td>
          <td colspan="3" class="column-team">
            <a>D-Junioren | Bezirksfreundschaftsspiele</a>
          </td>
          <td colspan="2">
            <a>FS | 550068375</a>
          </td>
        </tr>
        <tr class="odd">
          <td class="hidden-small"></td>
          <td class="column-club">
            <a class="club-wrapper">
              <div class="club-name">SGM VfB Neckarrems/&#8203;SKV Hochberg/&#8203;SGV Hochdorf I</div>
            </a>
          </td>
          <td class="column-colon">:</td>
          <td class="column-club no-border">
            <a class="club-wrapper">
              <div class="club-name">SV Fellbach III U12P</div>
            </a>
          </td>
          <td class="column-score"></td>
          <td class="column-detail"></td>
        </tr>
        <tr class="odd row-venue hidden-small">
          <td></td>
          <td colspan="3">Kunstrasenplatz, GWV-Sportpark (Kunstrasen), Hummelberg 4, 71686 Remseck am Neckar</td>
          <td></td>
        </tr>
        <tr class="row-competition hidden-small">
          <td class="column-date"><span class="hidden-small inline">So, 12.04.26 |&nbsp;</span>15:00</td>
          <td colspan="3" class="column-team">
            <a>Herren | Kreisliga A; Kreisliga</a>
          </td>
          <td colspan="2">
            <a>ME | 355926184</a>
          </td>
        </tr>
        <tr>
          <td class="hidden-small"></td>
          <td class="column-club">
            <a class="club-wrapper">
              <div class="club-name">SGM Hochberg/&#8203;Hochdorf</div>
            </a>
          </td>
          <td class="column-colon">:</td>
          <td class="column-club no-border">
            <a class="club-wrapper">
              <div class="club-name">VfB Neckarrems 1913 e.V.</div>
            </a>
          </td>
          <td class="column-score"></td>
          <td class="column-detail"></td>
        </tr>
        <tr class="row-venue hidden-small">
          <td></td>
          <td colspan="3">Rasenplatz, Waldallee 70, Waldallee 70, 71686 Remseck am Neckar</td>
          <td></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
"""


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

    def test_parses_real_matchplan_page_without_venue_rows(self):
        """The exact show-filter=false page has no venue rows, but games must still parse."""
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "text/html"}
        mock.text = _REAL_MATCHPLAN_HTML_WITHOUT_VENUES
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("00ES8GNAVO00000PVV0AG08LVUPGND5I")

        assert len(games) == 1
        assert games[0].date == "12.04.2026"
        assert games[0].time == "15:00"
        assert games[0].home_team == "SGM Hochberg/Hochdorf"
        assert games[0].guest_team == "VfB Neckarrems 1913 e.V."
        assert games[0].competition == "Herren | Kreisliga A; Kreisliga"
        assert games[0].venue_name == ""

    def test_parses_real_matchplan_page_and_extracts_venues(self):
        """show-venues=true adds row-venue rows that must be assigned to the previous game."""
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "text/html"}
        mock.text = _REAL_MATCHPLAN_HTML_WITH_VENUES
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("00ES8GNAVO00000PVV0AG08LVUPGND5I")

        assert len(games) == 2
        assert games[0].date == "11.04.2026"
        assert games[0].time == "12:00"
        assert games[0].home_team == "SGM VfB Neckarrems/SKV Hochberg/SGV Hochdorf I"
        assert games[0].guest_team == "SV Fellbach III U12P"
        assert games[0].venue_name == "Kunstrasenplatz, GWV-Sportpark (Kunstrasen), Hummelberg 4, 71686 Remseck am Neckar"
        assert games[1].date == "12.04.2026"
        assert games[1].time == "15:00"
        assert games[1].home_team == "SGM Hochberg/Hochdorf"
        assert games[1].guest_team == "VfB Neckarrems 1913 e.V."
        assert games[1].venue_name == "Rasenplatz, Waldallee 70, Waldallee 70, 71686 Remseck am Neckar"

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


# ---------------------------------------------------------------------------
# _normalize_venue_name
# ---------------------------------------------------------------------------

class TestNormalizeVenueName:
    def test_strips_whitespace(self):
        assert _normalize_venue_name("  Platz  ") == "platz"

    def test_lowercases(self):
        assert _normalize_venue_name("GWV-Sportpark") == "gwv-sportpark"

    def test_collapses_multiple_spaces(self):
        assert _normalize_venue_name("Platz  Nord") == "platz nord"

    def test_empty_string(self):
        assert _normalize_venue_name("") == ""


# ---------------------------------------------------------------------------
# filter_games_by_venue_configs
# ---------------------------------------------------------------------------

def _make_game(venue_id: str, venue_name: str) -> "ScrapedGame":
    from platzbelegung.models import ScrapedGame
    return ScrapedGame(
        venue_id=venue_id,
        venue_name=venue_name,
        date="01.04.2026",
        time="10:00",
        home_team="Home",
        guest_team="Away",
        competition="Liga",
        start_date="2026-04-01T10:00:00",
        scraped_at="",
    )


class TestFilterGamesByVenueConfigs:
    def _make_config(self, id="", name="", aliases=None, name_patterns=None):
        from platzbelegung.config import VenueConfig
        return VenueConfig(
            id=id,
            name=name,
            aliases=aliases or [],
            name_patterns=name_patterns or [],
        )

    def test_returns_all_when_no_configs(self):
        games = [_make_game("V1", "Platz 1")]
        assert filter_games_by_venue_configs(games, []) == games

    def test_filters_by_venue_id(self):
        games = [_make_game("V1", "Platz 1"), _make_game("V2", "Platz 2")]
        vc = self._make_config(id="V1")
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 1
        assert result[0].venue_id == "V1"

    def test_filters_by_alias_case_insensitive(self):
        games = [
            _make_game("", "GWV-Sportpark (Kunstrasen)"),
            _make_game("", "Rasenplatz"),
        ]
        vc = self._make_config(aliases=["gwv-sportpark (kunstrasen)"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 1
        assert result[0].venue_name == "GWV-Sportpark (Kunstrasen)"

    def test_alias_match_is_normalized(self):
        """Alias with different whitespace/casing should still match."""
        games = [_make_game("", "  Kirchweinbergweg  ")]
        vc = self._make_config(aliases=["Kirchweinbergweg"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 1

    def test_filters_by_name_pattern(self):
        games = [
            _make_game("", "GWV-Sportpark (Kunstrasen)"),
            _make_game("", "Kirchweinbergweg"),
            _make_game("", "Anderer Platz"),
        ]
        vc = self._make_config(name_patterns=["Kirchweinbergweg"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 1
        assert result[0].venue_name == "Kirchweinbergweg"

    def test_pattern_is_case_insensitive(self):
        games = [_make_game("", "GWV-Sportpark (Kunstrasen)")]
        vc = self._make_config(name_patterns=["gwv-sportpark"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 1

    def test_regex_pattern_partial_match(self):
        games = [
            _make_game("", "Kunstrasen Hochberg (GWV)"),
            _make_game("", "Rasenplatz Hochberg"),
            _make_game("", "Sportplatz Anderswo"),
        ]
        vc = self._make_config(name_patterns=["Hochberg"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 2

    def test_id_and_alias_in_same_config(self):
        games = [
            _make_game("V1", "Platz 1"),
            _make_game("V2", "Alias-Platz"),
            _make_game("V3", "Anderer"),
        ]
        vc = self._make_config(id="V1", aliases=["Alias-Platz"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 2

    def test_invalid_regex_pattern_is_skipped(self, caplog):
        import logging
        games = [_make_game("", "Platz")]
        vc = self._make_config(name_patterns=["[invalid"])
        with caplog.at_level(logging.WARNING, logger="platzbelegung.scraper"):
            result = filter_games_by_venue_configs(games, [vc])
        # Invalid pattern should be skipped without crash
        assert result == []
        assert any("Ungültiges Regex-Muster" in r.message for r in caplog.records)

    def test_unmatched_venues_logged(self, caplog):
        import logging
        games = [
            _make_game("V1", "Platz 1"),
            _make_game("V2", "Unmatched Platz"),
        ]
        vc = self._make_config(id="V1")
        with caplog.at_level(logging.DEBUG, logger="platzbelegung.scraper"):
            filter_games_by_venue_configs(games, [vc])
        assert any("Nicht gematchte" in r.message for r in caplog.records)

    def test_config_without_id_uses_alias(self):
        """Venue config with only aliases (no stable ID) should still match."""
        games = [
            _make_game("", "GWV-Sportpark (Kunstrasen)"),
            _make_game("SOME_ID", "Other Place"),
        ]
        vc = self._make_config(name="Kunstrasenplatz", aliases=["GWV-Sportpark (Kunstrasen)"])
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 1
        assert result[0].venue_name == "GWV-Sportpark (Kunstrasen)"

    def test_away_game_at_foreign_venue_excluded(self):
        """Auswärtsspiele auf fremden Plätzen werden durch Venue-Filter ausgeschlossen."""
        home_venue_game = _make_game("HOME_VENUE", "Heimstadion")
        away_venue_game = _make_game("AWAY_VENUE", "Gegnerplatz")
        vc = self._make_config(id="HOME_VENUE")
        result = filter_games_by_venue_configs(
            [home_venue_game, away_venue_game], [vc]
        )
        assert len(result) == 1
        assert result[0].venue_id == "HOME_VENUE"

    def test_only_home_venue_games_remain_after_filter(self):
        """Nach Venue-Filterung verbleiben nur Spiele auf den konfigurierten Plätzen."""
        games = [
            _make_game("V_HOME", "Kunstrasenplatz"),
            _make_game("V_AWAY1", "Gegnerplatz 1"),
            _make_game("V_AWAY2", "Gegnerplatz 2"),
            _make_game("V_HOME", "Kunstrasenplatz"),
        ]
        vc = self._make_config(id="V_HOME")
        result = filter_games_by_venue_configs(games, [vc])
        assert len(result) == 2
        assert all(g.venue_id == "V_HOME" for g in result)


# ---------------------------------------------------------------------------
# _is_placeholder_team
# ---------------------------------------------------------------------------

class TestIsPlaceholderTeam:
    def test_spielfrei_lowercase(self):
        assert _is_placeholder_team("spielfrei") is True

    def test_spielfrei_mixed_case(self):
        assert _is_placeholder_team("Spielfrei") is True
        assert _is_placeholder_team("SPIELFREI") is True

    def test_spielfrei_with_whitespace(self):
        assert _is_placeholder_team("  spielfrei  ") is True

    def test_bye(self):
        assert _is_placeholder_team("bye") is True
        assert _is_placeholder_team("BYE") is True

    def test_normal_team_name(self):
        assert _is_placeholder_team("SKV Hochberg") is False
        assert _is_placeholder_team("FC Muster") is False

    def test_empty_string(self):
        assert _is_placeholder_team("") is False


# ---------------------------------------------------------------------------
# Spielfrei-Filterung in den Parsern
# ---------------------------------------------------------------------------

_SPIELFREI_TABLE_HTML = """
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
        <td>04.04.2026</td>
        <td>11:00</td>
        <td>SKV Hochberg II</td>
        <td></td>
        <td>spielfrei</td>
        <td>Kreisliga B</td>
      </tr>
    </tbody>
  </table>
</body></html>
"""

_SPIELFREI_FIXTURE_HTML = """
<html><body>
  <h2 class="headline">Rasenplatz</h2>
  <div class="fixture-list-item">
    <span class="date">12.04.2026</span>
    <span class="time">11:00</span>
    <span class="home-team">TSV Alpha</span>
    <span class="guest-team">VfB Beta</span>
    <span class="competition">B-Junioren</span>
  </div>
  <div class="fixture-list-item">
    <span class="date">19.04.2026</span>
    <span class="time">11:00</span>
    <span class="home-team">TSV Alpha</span>
    <span class="guest-team">spielfrei</span>
    <span class="competition">B-Junioren</span>
  </div>
</body></html>
"""


class TestSpielfreiFilteringInTableParser:
    def test_spielfrei_row_excluded(self):
        """Zeile mit 'spielfrei' als Gegner darf keinen ScrapedGame-Eintrag erzeugen."""
        scraper = FussballDeScraper()
        with patch.object(
            scraper._session, "get", return_value=_mock_response(_SPIELFREI_TABLE_HTML)
        ):
            games = scraper.scrape_venue_games("VENUE001")

        assert len(games) == 1
        assert games[0].guest_team == "FC Muster"

    def test_spielfrei_uppercase_excluded(self):
        """'Spielfrei' in gemischter Groß-/Kleinschreibung wird ebenfalls gefiltert."""
        html = _SPIELFREI_TABLE_HTML.replace("spielfrei", "Spielfrei")
        scraper = FussballDeScraper()
        with patch.object(
            scraper._session, "get", return_value=_mock_response(html)
        ):
            games = scraper.scrape_venue_games("V1")

        assert len(games) == 1


class TestSpielfreiFilteringInFixtureParser:
    def test_spielfrei_fixture_excluded(self):
        """fixture-list-item mit 'spielfrei' als Gegner wird übersprungen."""
        scraper = FussballDeScraper()
        with patch.object(
            scraper._session, "get", return_value=_mock_response(_SPIELFREI_FIXTURE_HTML)
        ):
            games = scraper.scrape_venue_games("V2")

        assert len(games) == 1
        assert games[0].guest_team == "VfB Beta"


class TestSpielfreiFilteringInMatchplanJson:
    def test_spielfrei_in_json_excluded(self):
        """JSON-Matchplan-Einträge mit 'spielfrei' als Gegner werden übersprungen."""
        matchplan = {
            "matches": [
                {
                    "venue": {"id": "V1", "name": "Platz"},
                    "date": "01.04.2026",
                    "time": "14:00",
                    "homeTeam": {"name": "SKV Hochberg"},
                    "awayTeam": {"name": "FC Muster"},
                    "competition": {"name": "Liga"},
                },
                {
                    "venue": {"id": "V1", "name": "Platz"},
                    "date": "08.04.2026",
                    "time": "14:00",
                    "homeTeam": {"name": "SKV Hochberg"},
                    "awayTeam": {"name": "spielfrei"},
                    "competition": {"name": "Liga"},
                },
            ]
        }
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "application/json"}
        mock.json.return_value = matchplan
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert len(games) == 1
        assert games[0].guest_team == "FC Muster"

    def test_spielfrei_as_home_team_excluded(self):
        """JSON-Einträge mit 'spielfrei' als Heimteam werden ebenfalls übersprungen."""
        matchplan = {
            "matches": [
                {
                    "venue": {"id": "V1", "name": "Platz"},
                    "date": "01.04.2026",
                    "time": "14:00",
                    "homeTeam": {"name": "spielfrei"},
                    "awayTeam": {"name": "SKV Hochberg"},
                    "competition": {"name": "Liga"},
                },
            ]
        }
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "application/json"}
        mock.json.return_value = matchplan
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert games == []


class TestSpielfreiFilteringInMatchplanHtml:
    def test_spielfrei_in_html_matchplan_excluded(self):
        """HTML-Matchplan-Fragment mit 'spielfrei' als Gegner wird übersprungen."""
        html = """
        <div class="match-row" data-venue-id="V1">
            <span class="date">01.04.2026</span>
            <span class="time">14:00</span>
            <span class="home-team">SKV Hochberg</span>
            <span class="guest-team">FC Muster</span>
            <span class="competition">Liga</span>
            <span class="venue-name">Platz</span>
        </div>
        <div class="match-row" data-venue-id="V1">
            <span class="date">08.04.2026</span>
            <span class="time">14:00</span>
            <span class="home-team">SKV Hochberg</span>
            <span class="guest-team">spielfrei</span>
            <span class="competition">Liga</span>
            <span class="venue-name">Platz</span>
        </div>
        """
        scraper = FussballDeScraper()
        mock = MagicMock()
        mock.headers = {"content-type": "text/html"}
        mock.text = html
        mock.raise_for_status.return_value = None

        with patch.object(scraper._session, "get", return_value=mock):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert len(games) == 1
        assert games[0].guest_team == "FC Muster"
