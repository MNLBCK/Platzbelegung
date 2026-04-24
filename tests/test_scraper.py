"""Tests für den FussballDeScraper (scraper.py).

Der Scraper delegiert das gesamte HTML-Parsing an PHP (parse_matchplan.php).
Die Tests prüfen:
- Das korrekte Aufrufen des PHP-Subprozesses (über subprocess.run-Mock)
- Die Konvertierung der PHP-JSON-Ausgabe in ScrapedGame-Objekte
- Fehlerbehandlung (PHP nicht gefunden, Fehler-Exit-Code, ungültiges JSON)
- Die reinen Python-Hilfsfunktionen (Venue-Filterung, Normalisierung)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from platzbelegung.scraper import (
    FussballDeScraper,
    _find_php_script,
    _normalize_venue_name,
    filter_games_by_venue_configs,
    filter_games_by_venues,
)


# ---------------------------------------------------------------------------
# PHP-Skript-Suche
# ---------------------------------------------------------------------------

class TestFindPhpScript:
    def test_finds_script_in_package_directory(self):
        """parse_matchplan.php wird im Package-Verzeichnis gefunden (bundled standalone)."""
        script = _find_php_script()
        assert script is not None
        assert script.name == "parse_matchplan.php"
        assert script.exists()
        # The package-bundled version is in the same directory as scraper.py
        from pathlib import Path
        import platzbelegung.scraper as _mod
        pkg_dir = Path(_mod.__file__).parent
        assert script == pkg_dir / "parse_matchplan.php"

    def test_env_var_overrides_default(self, tmp_path, monkeypatch):
        """PLATZBELEGUNG_PHP_SCRIPT überschreibt den Standard-Pfad."""
        fake = tmp_path / "custom_parse.php"
        fake.write_text("<?php echo '[]';")
        monkeypatch.setenv("PLATZBELEGUNG_PHP_SCRIPT", str(fake))
        script = _find_php_script()
        assert script == fake

    def test_env_var_missing_file_ignored(self, monkeypatch):
        """Nicht existente Datei in PLATZBELEGUNG_PHP_SCRIPT wird ignoriert."""
        monkeypatch.setenv("PLATZBELEGUNG_PHP_SCRIPT", "/nonexistent/parse.php")
        # Sollte auf Standard-Pfad fallen zurück
        script = _find_php_script()
        # Kann None sein wenn auch Standardpfad fehlt, aber nicht crashen
        assert script is None or script.exists()

    def test_package_bundled_script_is_standalone(self):
        """Die im Package gebundelte parse_matchplan.php hat keine require-Abhängigkeit zu backend.php."""
        from pathlib import Path
        import platzbelegung.scraper as _mod
        pkg_script = Path(_mod.__file__).parent / "parse_matchplan.php"
        assert pkg_script.exists()
        content = pkg_script.read_text(encoding="utf-8")
        # Standalone: darf kein require __DIR__ . '/backend.php' haben
        assert "require __DIR__" not in content


# ---------------------------------------------------------------------------
# FussballDeScraper – scrape_club_matchplan via PHP-Subprocess
# ---------------------------------------------------------------------------

def _make_subprocess_result(
    stdout: bytes = b"[]",
    returncode: int = 0,
    stderr: bytes = b"",
) -> MagicMock:
    """Erstellt ein Mock-CompletedProcess-Objekt."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    mock.stderr = stderr
    return mock


_SAMPLE_PHP_OUTPUT = json.dumps([
    {
        "venueId": "kunstrasenplatz",
        "venueName": "Kunstrasenplatz",
        "date": "28.03.2026",
        "time": "14:00",
        "homeTeam": "SKV Hochberg",
        "guestTeam": "FC Muster",
        "competition": "Kreisliga A",
        "startDate": "2026-03-28T14:00:00+02:00",
        "homeLogoUrl": "",
        "guestLogoUrl": "",
        "result": "",
        "gameUrl": "",
    },
    {
        "venueId": "rasenplatz",
        "venueName": "Rasenplatz",
        "date": "05.04.2026",
        "time": "16:00",
        "homeTeam": "SKV Hochberg II",
        "guestTeam": "SV Test",
        "competition": "Kreisliga B",
        "startDate": "2026-04-05T16:00:00+02:00",
        "homeLogoUrl": "",
        "guestLogoUrl": "",
        "result": "",
        "gameUrl": "",
    },
]).encode()


class TestScrapeClubMatchplan:
    def test_calls_php_subprocess(self):
        """scrape_club_matchplan ruft php parse_matchplan.php mit korrekten Argumenten auf."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(_SAMPLE_PHP_OUTPUT)) as mock_run:
            games = scraper.scrape_club_matchplan("CLUB001")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list), "Erster Positional-Arg muss eine Liste sein"
        assert cmd[0] == "php"
        assert cmd[1].endswith("parse_matchplan.php")
        assert "--id=CLUB001" in cmd
        assert any(a.startswith("--date-from=") for a in cmd)
        assert any(a.startswith("--date-to=") for a in cmd)
        # scraper.timeout_seconds wird als --timeout weitergereicht (Fix P2)
        assert any(a.startswith("--timeout=") for a in cmd)

    def test_parses_php_json_output(self):
        """PHP-JSON-Ausgabe wird korrekt in ScrapedGame-Objekte konvertiert."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(_SAMPLE_PHP_OUTPUT)):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert len(games) == 2
        g = games[0]
        assert g.venue_id == "kunstrasenplatz"
        assert g.venue_name == "Kunstrasenplatz"
        assert g.date == "28.03.2026"
        assert g.time == "14:00"
        assert g.home_team == "SKV Hochberg"
        assert g.guest_team == "FC Muster"
        assert g.competition == "Kreisliga A"

    def test_scraped_at_is_set(self):
        """scraped_at wird für alle zurückgegebenen Spiele gesetzt."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(_SAMPLE_PHP_OUTPUT)):
            games = scraper.scrape_club_matchplan("CLUB001")

        for g in games:
            assert g.scraped_at  # nicht leer
            assert "T" in g.scraped_at  # sieht wie ISO 8601 aus

    def test_empty_output_returns_empty_list(self):
        """Leere PHP-Ausgabe ergibt leere Spiele-Liste."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(b"[]")):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert games == []

    def test_php_not_found_raises_runtime_error(self):
        """Fehlendes PHP-Binary löst RuntimeError aus."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", side_effect=FileNotFoundError("php not found")):
            with pytest.raises(RuntimeError, match="PHP-Binary"):
                scraper.scrape_club_matchplan("CLUB001")

    def test_php_script_not_found_raises_runtime_error(self):
        """Fehlendes parse_matchplan.php löst RuntimeError aus."""
        scraper = FussballDeScraper()
        scraper._php_script = None
        with pytest.raises(RuntimeError, match="parse_matchplan.php"):
            scraper.scrape_club_matchplan("CLUB001")

    def test_php_error_exit_raises_runtime_error(self):
        """Nicht-Null-Exit-Code vom PHP-Prozess löst RuntimeError aus."""
        scraper = FussballDeScraper()
        err_result = _make_subprocess_result(b"", returncode=1, stderr=b"Fehler beim Abrufen")
        with patch("subprocess.run", return_value=err_result):
            with pytest.raises(RuntimeError, match="PHP-Parser-Fehler"):
                scraper.scrape_club_matchplan("CLUB001")

    def test_invalid_json_raises_runtime_error(self):
        """Ungültige JSON-Ausgabe vom PHP-Prozess löst RuntimeError aus."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(b"not json")):
            with pytest.raises(RuntimeError, match="Ungültige JSON-Ausgabe"):
                scraper.scrape_club_matchplan("CLUB001")

    def test_limit_is_respected(self):
        """limit begrenzt die Anzahl der zurückgegebenen Spiele."""
        many_games = json.dumps([
            {
                "venueId": f"v{i}", "venueName": f"Platz {i}",
                "date": "01.04.2026", "time": "10:00",
                "homeTeam": f"Team {i}", "guestTeam": "Gegner",
                "competition": "Liga", "startDate": "2026-04-01T10:00:00+02:00",
            }
            for i in range(50)
        ]).encode()

        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(many_games)):
            games = scraper.scrape_club_matchplan("CLUB001", limit=10)

        assert len(games) == 10

    def test_max_parameter_passed_to_php(self):
        """--max wird als min(limit, 200) an PHP übergeben."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(b"[]")) as mock_run:
            scraper.scrape_club_matchplan("CLUB001", limit=50)

        cmd = mock_run.call_args[0][0]
        assert "--max=50" in cmd

    def test_max_capped_at_200(self):
        """--max wird auf maximal 200 begrenzt."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(b"[]")) as mock_run:
            scraper.scrape_club_matchplan("CLUB001", limit=999)

        cmd = mock_run.call_args[0][0]
        assert "--max=200" in cmd

    def test_timeout_raised_as_runtime_error(self):
        """TimeoutExpired wird in RuntimeError umgewandelt."""
        scraper = FussballDeScraper()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("php", 45)):
            with pytest.raises(RuntimeError, match="Timeout"):
                scraper.scrape_club_matchplan("CLUB001")

    def test_unknown_fields_in_php_output_ignored(self):
        """Unbekannte Felder in der PHP-Ausgabe (z.B. homeLogoUrl) werden ignoriert."""
        output = json.dumps([{
            "venueId": "v1", "venueName": "Platz",
            "date": "01.04.2026", "time": "10:00",
            "homeTeam": "Home", "guestTeam": "Away",
            "competition": "Liga", "startDate": "2026-04-01T10:00:00+02:00",
            "homeLogoUrl": "https://example.com/logo.png",
            "guestLogoUrl": "",
            "result": "2:1",
            "gameUrl": "https://www.fussball.de/spiel/...",
        }]).encode()
        scraper = FussballDeScraper()
        with patch("subprocess.run", return_value=_make_subprocess_result(output)):
            games = scraper.scrape_club_matchplan("CLUB001")

        assert len(games) == 1
        assert games[0].home_team == "Home"


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
