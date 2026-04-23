"""fussball.de Scraper – delegiert Parsing an PHP.

PHP (``parse_matchplan.php``) ist die einzige Source of Truth für das Parsen
der fussball.de-HTML-Struktur. Dieses Modul enthält nur noch:

- :class:`FussballDeScraper`: ruft ``parse_matchplan.php`` via Subprocess auf
  und konvertiert das JSON-Ergebnis in :class:`~platzbelegung.models.ScrapedGame`-Objekte.
- :func:`filter_games_by_venues`: filtert Spiele nach Sportstätten-IDs.
- :func:`filter_games_by_venue_configs`: filtert Spiele nach VenueConfig (ID, Alias, Muster).

Doppelte HTML-Parsing-Logik in Python wurde entfernt; sämtliche Normalisierung
und HTML-Parsing findet ausschließlich in ``backend.php`` /
``parse_matchplan.php`` statt.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from platzbelegung.config import ScraperConfig, get_date_range
from platzbelegung.models import ScrapedGame

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PHP-Skript-Suche
# ---------------------------------------------------------------------------

def _find_php_script() -> Path | None:
    """Sucht ``parse_matchplan.php`` in bekannten Verzeichnissen.

    Suchreihenfolge:
    1. Umgebungsvariable ``PLATZBELEGUNG_PHP_SCRIPT``
    2. Drei Ebenen über dieser Datei (Repo-Root beim Editable-Install)
    3. Aktuelles Arbeitsverzeichnis
    """
    env_path = os.environ.get("PLATZBELEGUNG_PHP_SCRIPT")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    candidate = Path(__file__).parent.parent.parent / "parse_matchplan.php"
    if candidate.exists():
        return candidate

    cwd_candidate = Path.cwd() / "parse_matchplan.php"
    if cwd_candidate.exists():
        return cwd_candidate

    return None


# ---------------------------------------------------------------------------
# Venue-Filterung (reine Python-Logik, keine HTML-Abhängigkeit)
# ---------------------------------------------------------------------------

def filter_games_by_venues(
    games: list[ScrapedGame], venue_ids: list[str]
) -> list[ScrapedGame]:
    """Filtert Spiele nach Sportstätten-IDs.

    Args:
        games: Liste von ScrapedGame-Objekten.
        venue_ids: Liste von Sportstätten-IDs (z.B. aus config.yaml).

    Returns:
        Gefilterte Liste mit nur Spielen auf den angegebenen Sportstätten.
    """
    if not venue_ids:
        return games
    venue_id_set = set(venue_ids)
    return [g for g in games if g.venue_id in venue_id_set]


def _normalize_venue_name(name: str) -> str:
    """Normalisiert einen Ortsnamen für den Vergleich."""
    return re.sub(r"\s+", " ", name.strip().lower())


def filter_games_by_venue_configs(
    games: list[ScrapedGame],
    venue_configs: list,
) -> list[ScrapedGame]:
    """Filtert Spiele nach Sportstätten-Konfigurationen (IDs, Aliases, Muster).

    Ein Spiel wird aufgenommen, wenn mindestens eine dieser Bedingungen zutrifft:
    - Die ``venue_id`` des Spiels stimmt mit der ``id`` in der Konfiguration überein.
    - Der normalisierte ``venue_name`` des Spiels stimmt mit einem normalisierten
      Alias aus der Konfiguration überein.
    - Der ``venue_name`` des Spiels passt auf ein Regex-Muster (``name_patterns``).

    Nicht gematchte Ortsnamen werden auf DEBUG-Ebene protokolliert.

    Args:
        games: Liste von ScrapedGame-Objekten.
        venue_configs: Liste von :class:`~platzbelegung.config.VenueConfig`-Objekten.

    Returns:
        Gefilterte Liste der passenden Spiele.
    """
    if not venue_configs:
        return games

    compiled: list[tuple] = []
    for vc in venue_configs:
        patterns = []
        for pat in getattr(vc, "name_patterns", []):
            try:
                patterns.append(re.compile(pat, re.IGNORECASE))
            except re.error as exc:
                logger.warning("Ungültiges Regex-Muster '%s': %s", pat, exc)
        compiled.append((vc, patterns))

    matched: list[ScrapedGame] = []
    unmatched_names: set[str] = set()

    for game in games:
        game_venue_id = game.venue_id
        game_venue_name = game.venue_name
        game_venue_norm = _normalize_venue_name(game_venue_name)
        match_found = False

        for vc, patterns in compiled:
            if getattr(vc, "id", "") and game_venue_id == vc.id:
                match_found = True
                break

            for alias in getattr(vc, "aliases", []):
                if _normalize_venue_name(alias) == game_venue_norm:
                    match_found = True
                    break
            if match_found:
                break

            for pat in patterns:
                if pat.search(game_venue_name):
                    match_found = True
                    break
            if match_found:
                break

        if match_found:
            matched.append(game)
        else:
            unmatched_names.add(game_venue_name)

    if unmatched_names:
        logger.debug(
            "Nicht gematchte Ortsnamen (nicht in Konfiguration): %s",
            sorted(unmatched_names),
        )

    return matched


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class FussballDeScraper:
    """Scrapt Spielplandaten von fussball.de via PHP-Parser.

    Das gesamte HTML-Parsing findet in ``parse_matchplan.php`` statt.
    Diese Klasse ist nur für den Aufruf des PHP-Subprozesses und die
    Konvertierung des JSON-Ergebnisses in Python-Objekte zuständig.
    """

    def __init__(self, cfg: ScraperConfig | None = None) -> None:
        self._cfg = cfg or ScraperConfig()
        self._php_script = _find_php_script()

    # ------------------------------------------------------------------
    # Öffentliche Methoden – Club Matchplan
    # ------------------------------------------------------------------

    def scrape_club_matchplan(
        self,
        club_id: str,
        season: str | None = None,
        limit: int = 100,
    ) -> list[ScrapedGame]:
        """Scrapt alle Spiele eines Vereins über ``parse_matchplan.php``.

        Das Parsing der fussball.de-HTML-Antwort erfolgt ausschließlich in
        PHP (``parse_matchplan.php``). Python liest das resultierende JSON
        und konvertiert es in :class:`~platzbelegung.models.ScrapedGame`-Objekte.

        Args:
            club_id: ID des Vereins (aus der fussball.de-URL).
            season: Nicht mehr verwendet (Datum wird aus ``get_date_range()`` ermittelt).
            limit: Maximale Anzahl der zu ladenden Spiele.

        Returns:
            Liste der gefundenen Spiele als ScrapedGame-Objekte.

        Raises:
            RuntimeError: Wenn ``parse_matchplan.php`` nicht gefunden wird oder
                der PHP-Prozess einen Fehler meldet.
        """
        if self._php_script is None:
            raise RuntimeError(
                "parse_matchplan.php nicht gefunden. "
                "Bitte sicherstellen, dass das Skript im Projekt-Root liegt oder "
                "PLATZBELEGUNG_PHP_SCRIPT auf den korrekten Pfad zeigt."
            )

        date_from, date_to = get_date_range()
        scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.debug(
            "Scraping club matchplan via PHP: %s (%s – %s)",
            club_id, date_from, date_to,
        )

        try:
            result = subprocess.run(
                [
                    "php",
                    str(self._php_script),
                    f"--id={club_id}",
                    f"--date-from={date_from.strftime('%Y-%m-%d')}",
                    f"--date-to={date_to.strftime('%Y-%m-%d')}",
                    f"--max={min(limit, 200)}",
                ],
                capture_output=True,
                # PHP macht intern einen HTTP-Request an fussball.de; der PHP-Prozess
                # benötigt zusätzlich zur konfigurierten HTTP-Timeout-Zeit noch Zeit
                # für Prozessstart und HTML-Parsing, daher 30 Sekunden Puffer.
                timeout=self._cfg.timeout_seconds + 30,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"PHP-Parser-Timeout nach {exc.timeout}s für Verein {club_id}"
            ) from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                "PHP-Binary nicht gefunden. Bitte PHP 8.1+ installieren."
            ) from exc

        if result.returncode != 0:
            err = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"PHP-Parser-Fehler (Exit {result.returncode}): {err}")

        try:
            games_data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Ungültige JSON-Ausgabe vom PHP-Parser: {exc}"
            ) from exc

        if not isinstance(games_data, list):
            logger.warning("PHP-Parser lieferte kein Array zurück")
            return []

        games = [
            ScrapedGame.from_dict(g, scraped_at)
            for g in games_data
            if isinstance(g, dict)
        ]

        logger.info(
            "Club %s: %d Spiel(e) gefunden über PHP-Parser", club_id, len(games)
        )
        return games[:limit]
