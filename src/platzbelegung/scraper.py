"""Direkter fussball.de HTML-Scraper.

Scrapt Spielplandaten direkt von den öffentlichen fussball.de-Seiten,
ohne eine zwischengeschaltete REST-API.  Entspricht der Logik, die
zuvor in ``server.js`` (Node.js) implementiert war.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote as _url_quote

import requests
from bs4 import BeautifulSoup, Tag

from platzbelegung.config import ScraperConfig
from platzbelegung.models import ScrapedGame

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_TIME_RE = re.compile(r"(\d{2}):(\d{2})")
_VENUE_ID_RE = re.compile(r"/id/([^/?#]+)")


def _safe_text(el: Optional[Tag]) -> str:
    """Gibt den Text eines Elements zurück oder einen leeren String."""
    return el.get_text(strip=True) if el else ""


def _parse_german_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Parst ein deutsches Datum und eine Uhrzeit zu einem datetime-Objekt."""
    m = _DATE_RE.search(date_str)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    t = _TIME_RE.search(time_str or "")
    hour = int(t.group(1)) if t else 0
    minute = int(t.group(2)) if t else 0
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


class FussballDeScraper:
    """Scrapt Spielplandaten direkt von fussball.de."""

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

    # ------------------------------------------------------------------
    # Öffentliche Methoden
    # ------------------------------------------------------------------

    def scrape_venue_games(self, venue_id: str) -> list[ScrapedGame]:
        """Scrapt alle Spiele für eine Sportstätte von fussball.de.

        Args:
            venue_id: ID der Sportstätte (aus der fussball.de-URL).

        Returns:
            Liste der gefundenen Spiele als ScrapedGame-Objekte.
        """
        url = f"{self._cfg.fussball_de_base}/sportstaette/-/id/{venue_id}"
        # Batch scrape time – shared across all games scraped in this call
        scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.debug("Scraping venue %s: %s", venue_id, url)

        response = self._session.get(url, timeout=self._cfg.timeout_seconds)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Seitenname aus Überschrift
        h1 = soup.find("h1", class_="headline")
        h2 = soup.find("h2", class_="headline")
        venue_name = (
            _safe_text(h1)
            or _safe_text(h2)
            or f"Sportstätte {venue_id}"
        )

        games = self._parse_table_rows(soup, venue_id, venue_name, scraped_at)
        if not games:
            games = self._parse_fixture_items(soup, venue_id, venue_name, scraped_at)

        logger.info(
            "Venue %s (%s): %d Spiel(e) gefunden", venue_id, venue_name, len(games)
        )
        return games

    def search_venues(self, query: str) -> list[dict]:
        """Sucht nach Sportstätten auf fussball.de.

        Args:
            query: Suchbegriff (mind. 2 Zeichen).

        Returns:
            Liste der Suchergebnisse als Dicts mit 'id', 'name', 'location', 'url'.
        """
        url = (
            f"{self._cfg.fussball_de_base}/suche/-/suche/"
            f"{_url_quote(query)}/typ/sportstaette"
        )
        logger.debug("Searching venues: %s", url)

        response = self._session.get(url, timeout=self._cfg.timeout_seconds)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        venues = []

        for item in soup.select(".search-result-item, .result-item"):
            link = item.select_one("a")
            if not link:
                continue
            href = link.get("href", "")
            name = _safe_text(link) or _safe_text(item.select_one(".title"))
            location = _safe_text(item.select_one(".location, .subtitle"))

            id_match = _VENUE_ID_RE.search(href)
            if not id_match or not name:
                continue

            venues.append(
                {
                    "id": id_match.group(1),
                    "name": name,
                    "location": location,
                    "url": (
                        href
                        if href.startswith("http")
                        else f"{self._cfg.fussball_de_base}{href}"
                    ),
                }
            )

        return venues

    # ------------------------------------------------------------------
    # Interne Parser
    # ------------------------------------------------------------------

    def _parse_table_rows(
        self,
        soup: BeautifulSoup,
        venue_id: str,
        venue_name: str,
        scraped_at: str,
    ) -> list[ScrapedGame]:
        """Parst Spielzeilen aus Tabellen (primäres Layout)."""
        games: list[ScrapedGame] = []
        for row in soup.select("table.table-striped tbody tr, .result-set-row"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            date_text = cells[0].get_text(strip=True)
            time_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            home_team = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            guest_team = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            competition = cells[5].get_text(strip=True) if len(cells) > 5 else ""

            if not date_text or not home_team:
                continue

            start_dt = _parse_german_datetime(date_text, time_text)
            if not start_dt:
                continue

            games.append(
                ScrapedGame(
                    venue_id=venue_id,
                    venue_name=venue_name,
                    date=date_text,
                    time=time_text,
                    home_team=home_team,
                    guest_team=guest_team,
                    competition=competition,
                    start_date=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    scraped_at=scraped_at,
                )
            )
        return games

    def _parse_fixture_items(
        self,
        soup: BeautifulSoup,
        venue_id: str,
        venue_name: str,
        scraped_at: str,
    ) -> list[ScrapedGame]:
        """Parst Spieleinträge aus alternativen Layout-Elementen (Fallback)."""
        games: list[ScrapedGame] = []
        for item in soup.select(".fixture-list-item, .match-row, .game-row"):
            date_text = _safe_text(item.select_one(".date, .match-date"))
            time_text = _safe_text(item.select_one(".time, .match-time"))
            home_team = _safe_text(item.select_one(".home-team, .team-home"))
            guest_team = _safe_text(item.select_one(".guest-team, .team-guest"))
            competition = _safe_text(item.select_one(".competition, .league"))

            if not date_text or not home_team:
                continue

            start_dt = _parse_german_datetime(date_text, time_text)
            if not start_dt:
                continue

            games.append(
                ScrapedGame(
                    venue_id=venue_id,
                    venue_name=venue_name,
                    date=date_text,
                    time=time_text,
                    home_team=home_team,
                    guest_team=guest_team,
                    competition=competition,
                    start_date=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    scraped_at=scraped_at,
                )
            )
        return games
