"""Konfiguration für die Platzbelegungs-Übersicht.

Die Konfiguration wird aus ``config.yaml`` im Projektverzeichnis geladen.
Enthält das Projekt keine ``config.yaml``, werden eingebettete Standardwerte
verwendet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Konfigurationsklassen
# ---------------------------------------------------------------------------

@dataclass
class ClubConfig:
    """Konfiguration eines Vereins mit Trainingszeiten-URL."""
    name: str = ""
    training_url: str = ""
    venue_name: str = ""


@dataclass
class VenueConfig:
    """Eine konfigurierte Sportstätte."""
    id: str = ""
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    name_patterns: list[str] = field(default_factory=list)


@dataclass
class DateRangeConfig:
    """Zeitraum-Konfiguration."""
    mode: str = "auto"          # "auto" oder "manual"
    start: date | None = None
    end: date | None = None


@dataclass
class ScraperConfig:
    """Scraper-Einstellungen."""
    fussball_de_base: str = "https://www.fussball.de"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    timeout_seconds: int = 15
    preparation_buffer_minutes: int = 15
    default_game_duration_minutes: int = 90
    game_durations: dict[str, int] = field(default_factory=lambda: {
        "Herren": 90,
        "A-Junioren": 70,
        "B-Junioren": 70,
        "C-Junioren": 60,
        "D-Junioren": 50,
        "E-Junioren": 40,
        "F-Junioren": 30,
    })


@dataclass
class OutputConfig:
    """Ausgabe-Pfade."""
    data_dir: str = "data"
    snapshots_dir: str = "data/snapshots"
    html_file: str = "data/latest.html"


@dataclass
class AppConfig:
    """Vollständige Anwendungskonfiguration."""
    club_id: str = "00ES8GNAVO00000PVV0AG08LVUPGND5I"
    club_name: str = ""
    season: str = "2526"
    venues: list[VenueConfig] = field(default_factory=list)
    clubs: list[ClubConfig] = field(default_factory=list)
    date_range: DateRangeConfig = field(default_factory=DateRangeConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


# ---------------------------------------------------------------------------
# config.yaml laden
# ---------------------------------------------------------------------------

def _find_config_file() -> Path | None:
    """Sucht nach config.yaml im Projektverzeichnis."""
    env_path = os.environ.get("PLATZBELEGUNG_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    # config.yaml im Repo-Root (drei Ebenen über dieser Datei)
    candidate = Path(__file__).parent.parent.parent / "config.yaml"
    if candidate.exists():
        return candidate
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not _YAML_AVAILABLE:
        raise ImportError(
            "PyYAML ist nicht installiert. Bitte 'pip install pyyaml' ausführen."
        )
    with open(path, encoding="utf-8") as f:
        return _yaml.safe_load(f) or {}


def _parse_date_range(raw: dict[str, Any]) -> DateRangeConfig:
    mode = raw.get("mode", "auto")
    start = end = None
    if mode == "manual":
        raw_start = raw.get("start")
        raw_end = raw.get("end")
        if raw_start:
            start = date.fromisoformat(str(raw_start))
        if raw_end:
            end = date.fromisoformat(str(raw_end))
    return DateRangeConfig(mode=mode, start=start, end=end)


def load_config(path: Path | None = None) -> AppConfig:
    """Lädt die AppConfig aus config.yaml.

    Gibt Standardkonfiguration zurück, wenn keine config.yaml vorhanden ist.
    """
    if path is None:
        path = _find_config_file()

    raw: dict[str, Any] = {}
    if path is not None:
        raw = _load_yaml(path)

    club = raw.get("club", {})
    sc_raw = raw.get("scraper", {})
    out_raw = raw.get("output", {})

    _sc_defaults = ScraperConfig()
    game_durations = {**_sc_defaults.game_durations, **sc_raw.get("game_durations", {})}
    scraper = ScraperConfig(
        fussball_de_base=sc_raw.get("fussball_de_base", _sc_defaults.fussball_de_base),
        user_agent=sc_raw.get("user_agent", _sc_defaults.user_agent),
        timeout_seconds=int(sc_raw.get("timeout_seconds", _sc_defaults.timeout_seconds)),
        preparation_buffer_minutes=int(
            sc_raw.get("preparation_buffer_minutes", _sc_defaults.preparation_buffer_minutes)
        ),
        default_game_duration_minutes=int(
            sc_raw.get("default_game_duration_minutes", _sc_defaults.default_game_duration_minutes)
        ),
        game_durations=game_durations,
    )

    _out_defaults = OutputConfig()
    output = OutputConfig(
        data_dir=out_raw.get("data_dir", _out_defaults.data_dir),
        snapshots_dir=out_raw.get("snapshots_dir", _out_defaults.snapshots_dir),
        html_file=out_raw.get("html_file", _out_defaults.html_file),
    )

    venues = [
        VenueConfig(
            id=v.get("id", ""),
            name=v.get("name", ""),
            aliases=v.get("aliases", []) if isinstance(v.get("aliases"), list) else [],
            name_patterns=v.get("name_patterns", []) if isinstance(v.get("name_patterns"), list) else [],
        )
        for v in raw.get("venues", [])
        if isinstance(v, dict) and (
            v.get("id") or v.get("name") or v.get("aliases") or v.get("name_patterns")
        )
    ]

    clubs = [
        ClubConfig(
            name=c.get("name", ""),
            training_url=c.get("training_url", ""),
            venue_name=c.get("venue_name", ""),
        )
        for c in raw.get("clubs", [])
        if isinstance(c, dict) and (c.get("name") or c.get("training_url"))
    ]

    return AppConfig(
        club_id=club.get("id", "00ES8GNAVO00000PVV0AG08LVUPGND5I"),
        club_name=club.get("name", ""),
        season=str(raw.get("season", "2526")),
        venues=venues,
        clubs=clubs,
        date_range=_parse_date_range(raw.get("date_range", {})),
        scraper=scraper,
        output=output,
    )


# ---------------------------------------------------------------------------
# Modulweite Singleton-Konfiguration
# ---------------------------------------------------------------------------

_app_config: AppConfig = load_config()


# ---------------------------------------------------------------------------
# Zeitraum-Berechnung
# ---------------------------------------------------------------------------

def get_date_range() -> tuple[date, date]:
    """Gibt den Zeitraum zurück, der abgefragt werden soll.

    Der Zeitraum umfasst den aktuellen Monat sowie den Monat, der in
    3 Wochen beginnt (kann der gleiche oder der nächste Monat sein).
    Zurückgegeben wird (erster_tag, letzter_tag) des gesamten Bereichs.
    """
    cfg = _app_config
    if cfg.date_range.mode == "manual" and cfg.date_range.start and cfg.date_range.end:
        return cfg.date_range.start, cfg.date_range.end

    today = date.today()
    in_three_weeks = today + timedelta(weeks=3)

    start = today.replace(day=1)

    # Letzter Tag des Monats, der in 3 Wochen liegt
    if in_three_weeks.month == 12:
        end = in_three_weeks.replace(day=31)
    else:
        end = in_three_weeks.replace(
            month=in_three_weeks.month + 1, day=1
        ) - timedelta(days=1)

    return start, end
