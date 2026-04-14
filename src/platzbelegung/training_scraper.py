"""Scraper für Trainingszeiten von Vereinswebseiten.

Lädt und parst die Trainingszeiten-Seiten der konfigurierten Vereine.
Unterstützt verschiedene HTML-Layouts (Tabellen, Listen, strukturierter Text).

Die gefundene Quell-URL wird in jedem :class:`~platzbelegung.models.TrainingSession`-
Objekt gespeichert, damit die HTML-Ausgabe auf die Ursprungsseite verlinken kann.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from platzbelegung.config import ClubConfig, ScraperConfig
from platzbelegung.models import TrainingSession

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"(\d{1,2})[:\.](\d{2})")

# Deutsch → int (Montag=0, Sonntag=6)
_WEEKDAY_MAP: dict[str, int] = {
    "montag": 0, "mo": 0,
    "dienstag": 1, "di": 1,
    "mittwoch": 2, "mi": 2,
    "donnerstag": 3, "do": 3,
    "freitag": 4, "fr": 4,
    "samstag": 5, "sa": 5,
    "sonntag": 6, "so": 6,
}

_WEEKDAY_RE = re.compile(
    r"\b(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|"
    r"mo|di|mi|do|fr|sa|so)\.?\b",
    re.IGNORECASE,
)

# Gängige deutsche Begriffe für Trainingszeiten-Sektionen
_TRAINING_SECTION_RE = re.compile(
    r"training(szeiten|splan|szeit|sbetrieb)?|trainings|übungsleiter",
    re.IGNORECASE,
)

# Begriffe, die auf Mannschaftsnamen hinweisen
_TEAM_KEYWORDS_RE = re.compile(
    r"herren|damen|junioren|jugend|senior|aktive|reserve|"
    r"mädchen|männer|frauen|u\s*\d{1,2}|a-|b-|c-|d-|e-|f-|g-|bambini",
    re.IGNORECASE,
)


def _parse_time(text: str) -> Optional[time]:
    """Parst eine Uhrzeit aus einem Text-String."""
    m = _TIME_RE.search(text)
    if not m:
        return None
    try:
        return time(int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def _parse_time_range(text: str) -> tuple[Optional[time], Optional[time]]:
    """Parst einen Zeitraum wie '18:00 – 20:00' oder '18:00-20:00'."""
    times = _TIME_RE.findall(text)
    start: Optional[time] = None
    end: Optional[time] = None
    if len(times) >= 1:
        try:
            start = time(int(times[0][0]), int(times[0][1]))
        except ValueError:
            pass
    if len(times) >= 2:
        try:
            end = time(int(times[1][0]), int(times[1][1]))
        except ValueError:
            pass
    return start, end


def _parse_weekday(text: str) -> Optional[int]:
    """Extrahiert den ersten Wochentag aus einem Text."""
    m = _WEEKDAY_RE.search(text)
    if not m:
        return None
    return _WEEKDAY_MAP.get(m.group(1).lower().rstrip("."))


def _compute_duration(start: time, end: Optional[time]) -> int:
    """Berechnet die Dauer in Minuten zwischen start und end."""
    if end is None:
        return 90
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    diff = end_min - start_min
    return diff if diff > 0 else 90


def _safe_text(el: Optional[Tag]) -> str:
    """Gibt den Text eines Elements zurück oder einen leeren String."""
    if el is None:
        return ""
    return el.get_text(" ", strip=True).replace("\u200b", "")


class ClubWebsiteScraper:
    """Scrapt Trainingszeiten von Vereinswebseiten.

    Die Klasse implementiert eine heuristische Parsing-Strategie:
    1. Suche nach ``<table>``-Elementen, die Wochentag + Uhrzeit + Team enthalten.
    2. Suche nach ``<li>`` / ``<p>``-Elementen mit Wochentag + Uhrzeit.
    3. Zeilenweises Parsen des gesamten Seitentexts als Fallback.
    """

    def __init__(self, cfg: ScraperConfig | None = None) -> None:
        self._cfg = cfg or ScraperConfig()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self._cfg.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
        )

    def scrape_club(
        self, club_cfg: ClubConfig
    ) -> list[TrainingSession]:
        """Scrapt die Trainingszeiten eines Vereins.

        Args:
            club_cfg: Konfiguration des Vereins (Name, URL, Sportstätte).

        Returns:
            Liste der gefundenen Trainingseinheiten.
        """
        if not club_cfg.training_url:
            logger.debug("Keine training_url für Verein '%s'", club_cfg.name)
            return []

        scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.debug(
            "Scraping Trainingszeiten für %s: %s", club_cfg.name, club_cfg.training_url
        )

        try:
            response = self._session.get(
                club_cfg.training_url, timeout=self._cfg.timeout_seconds
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Netzwerkfehler beim Laden von %s (%s): %s",
                club_cfg.training_url, type(exc).__name__, exc,
            )
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        sessions = self._parse_training_page(
            soup,
            club_name=club_cfg.name,
            venue_name=club_cfg.venue_name,
            source_url=club_cfg.training_url,
            scraped_at=scraped_at,
        )

        logger.info(
            "%s (%s): %d Trainingseinheit(en) gefunden",
            club_cfg.name, club_cfg.training_url, len(sessions),
        )
        return sessions

    # ------------------------------------------------------------------
    # Interne Parser
    # ------------------------------------------------------------------

    def _parse_training_page(
        self,
        soup: BeautifulSoup,
        club_name: str,
        venue_name: str,
        source_url: str,
        scraped_at: str,
    ) -> list[TrainingSession]:
        """Parst eine HTML-Seite nach Trainingszeiten."""
        sessions: list[TrainingSession] = []

        # Strategie 1: Tabellen mit Trainingszeiten
        sessions.extend(
            self._parse_training_tables(
                soup, club_name, venue_name, source_url, scraped_at
            )
        )

        # Strategie 2: Listen/Paragraphen – nur wenn Tabellen nichts lieferten
        if not sessions:
            sessions.extend(
                self._parse_training_lists(
                    soup, club_name, venue_name, source_url, scraped_at
                )
            )

        # Strategie 3: Zeilenweises Parsen des Volltext-Inhalts als Fallback
        if not sessions:
            sessions.extend(
                self._parse_training_text(
                    soup, club_name, venue_name, source_url, scraped_at
                )
            )

        # Duplikate entfernen (gleicher Wochentag + Startzeit + Team)
        seen: set[tuple] = set()
        unique: list[TrainingSession] = []
        for s in sessions:
            key = (s.weekday, s.start_time, s.team_name.lower())
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique

    def _parse_training_tables(
        self,
        soup: BeautifulSoup,
        club_name: str,
        venue_name: str,
        source_url: str,
        scraped_at: str,
    ) -> list[TrainingSession]:
        """Parst Trainingszeiten aus HTML-Tabellen."""
        sessions: list[TrainingSession] = []

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue

            # Prüfe ob die Tabelle überhaupt Trainings-relevante Inhalte enthält
            table_text = _safe_text(table)
            has_weekday = bool(_WEEKDAY_RE.search(table_text))
            has_time = bool(_TIME_RE.search(table_text))
            if not (has_weekday and has_time):
                continue

            # Kopfzeile analysieren, um Spaltenrollen zu bestimmen
            header_row = rows[0]
            header_cells = [_safe_text(c).lower() for c in header_row.find_all(["th", "td"])]
            col_weekday = col_time = col_team = col_venue = -1
            for i, h in enumerate(header_cells):
                if any(k in h for k in ("tag", "wochentag", "woche")):
                    col_weekday = i
                elif any(k in h for k in ("uhrzeit", "zeit", "von", "beginn")):
                    col_time = i
                elif any(k in h for k in ("mannschaft", "gruppe", "team", "abteilung")):
                    col_team = i
                elif any(k in h for k in ("platz", "ort", "halle", "sportstätte")):
                    col_venue = i

            data_rows = rows[1:] if col_weekday >= 0 or col_time >= 0 else rows
            for row in data_rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                texts = [_safe_text(c) for c in cells]

                # Wochentag extrahieren
                weekday_text = texts[col_weekday] if col_weekday >= 0 and col_weekday < len(texts) else " ".join(texts)
                weekday = _parse_weekday(weekday_text)
                if weekday is None:
                    # Wochentag aus dem gesamten Zeilentext suchen
                    weekday = _parse_weekday(" ".join(texts))
                if weekday is None:
                    continue

                # Uhrzeit extrahieren
                time_text = texts[col_time] if col_time >= 0 and col_time < len(texts) else " ".join(texts)
                start, end = _parse_time_range(time_text)
                if start is None:
                    start, end = _parse_time_range(" ".join(texts))
                if start is None:
                    continue

                # Mannschaft extrahieren
                if col_team >= 0 and col_team < len(texts):
                    team_name = texts[col_team].strip()
                else:
                    # Heuristik: erste Zelle, die wie ein Team aussieht
                    team_name = next(
                        (t for t in texts if _TEAM_KEYWORDS_RE.search(t)),
                        club_name,
                    )

                # Sportstätte extrahieren
                row_venue = venue_name
                if col_venue >= 0 and col_venue < len(texts) and texts[col_venue]:
                    row_venue = texts[col_venue].strip()

                sessions.append(
                    TrainingSession(
                        club_name=club_name,
                        team_name=team_name or club_name,
                        weekday=weekday,
                        start_time=start,
                        end_time=end,
                        venue_name=row_venue,
                        source_url=source_url,
                        scraped_at=scraped_at,
                        duration_minutes=_compute_duration(start, end),
                    )
                )

        return sessions

    def _parse_training_lists(
        self,
        soup: BeautifulSoup,
        club_name: str,
        venue_name: str,
        source_url: str,
        scraped_at: str,
    ) -> list[TrainingSession]:
        """Parst Trainingszeiten aus Listen- und Absatzelementen."""
        sessions: list[TrainingSession] = []
        current_team = club_name

        # Relevante Sektionen finden: Überschriften + nachfolgende Inhalte
        for el in soup.find_all(["h1", "h2", "h3", "h4", "li", "p", "div"]):
            text = _safe_text(el)
            if not text:
                continue

            # Überschrift mit Mannschaftsname?
            if el.name in ("h1", "h2", "h3", "h4"):
                if _TEAM_KEYWORDS_RE.search(text):
                    current_team = text.strip()
                continue

            # Nur wenn Wochentag + Uhrzeit in einer Zeile vorkommt
            weekday = _parse_weekday(text)
            if weekday is None:
                continue
            start, end = _parse_time_range(text)
            if start is None:
                continue

            # Mannschaft ggf. aus Text extrahieren
            team_match = _TEAM_KEYWORDS_RE.search(text)
            team_name = team_match.group(0).strip() if team_match else current_team

            sessions.append(
                TrainingSession(
                    club_name=club_name,
                    team_name=team_name,
                    weekday=weekday,
                    start_time=start,
                    end_time=end,
                    venue_name=venue_name,
                    source_url=source_url,
                    scraped_at=scraped_at,
                    duration_minutes=_compute_duration(start, end),
                )
            )

        return sessions

    def _parse_training_text(
        self,
        soup: BeautifulSoup,
        club_name: str,
        venue_name: str,
        source_url: str,
        scraped_at: str,
    ) -> list[TrainingSession]:
        """Fallback: Parst Trainingszeiten aus dem Volltext der Seite."""
        sessions: list[TrainingSession] = []
        current_team = club_name

        # Gesamttext zeilenweise durchgehen
        text = soup.get_text("\n", strip=True)
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Aktuellen Mannschaftskontext aktualisieren
            if _TEAM_KEYWORDS_RE.search(line) and not _TIME_RE.search(line):
                current_team = line
                continue

            weekday = _parse_weekday(line)
            if weekday is None:
                continue
            start, end = _parse_time_range(line)
            if start is None:
                continue

            sessions.append(
                TrainingSession(
                    club_name=club_name,
                    team_name=current_team,
                    weekday=weekday,
                    start_time=start,
                    end_time=end,
                    venue_name=venue_name,
                    source_url=source_url,
                    scraped_at=scraped_at,
                    duration_minutes=_compute_duration(start, end),
                )
            )

        return sessions


def scrape_from_training_sources(sources_path: str | None = None, cfg: ScraperConfig | None = None) -> list[TrainingSession]:
    """Lädt eine Liste genehmigter Trainingsquellen aus `data/training_sources.json`
    und führt den `ClubWebsiteScraper` für jede Quelle aus.

    Args:
        sources_path: Pfad zur JSON-Datei mit Quellen. Falls None, wird
            `../data/training_sources.json` relativ zum Paket-Root verwendet.
        cfg: Optionaler `ScraperConfig` zur Weitergabe an den Scraper.

    Returns:
        Eine Liste aller gefundenen `TrainingSession`-Objekte aller Quellen.
    """
    import os, json
    from types import SimpleNamespace

    if sources_path is None:
        pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sources_path = os.path.join(pkg_root, "data", "training_sources.json")

    try:
        with open(sources_path, "r", encoding="utf-8") as f:
            sources = json.load(f)
    except FileNotFoundError:
        logger.debug("training_sources.json nicht gefunden: %s", sources_path)
        return []
    except Exception as exc:
        logger.warning("Fehler beim Laden von %s: %s", sources_path, exc)
        return []

    scraper = ClubWebsiteScraper(cfg)
    all_sessions: list[TrainingSession] = []

    for entry in sources:
        url = entry.get("source_url")
        if not url:
            continue
        club_name = entry.get("club_name") or entry.get("club") or url
        venue_name = entry.get("venue") or entry.get("venue_name") or ""
        # einfache duck-typed Config/Club-Objekt
        club_obj = SimpleNamespace(name=club_name, training_url=url, venue_name=venue_name)
        try:
            sessions = scraper.scrape_club(club_obj)
            all_sessions.extend(sessions)
        except Exception:
            logger.exception("Fehler beim Scrapen von %s", url)

    # remove duplicates across sources
    seen = set()
    unique: list[TrainingSession] = []
    for s in all_sessions:
        key = (s.club_name, s.team_name, s.weekday, s.start_time)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique
