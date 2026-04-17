"""Direkter fussball.de Scraper.

Scrapt Spielplandaten direkt von fussball.de, primär über die AJAX-API
für Vereins-Matchpläne (ajax.club.matchplan). Diese Methode ist stabiler
als das Scrapen von Sportstätten-Seiten, da die HTML-Struktur sich
häufiger ändert.

Die venue-basierte Scraping-Methode ist weiterhin als Fallback verfügbar,
sollte aber nur verwendet werden, wenn die club-basierte Methode nicht
funktioniert.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote as _url_quote
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from platzbelegung.config import ScraperConfig
from platzbelegung.models import ScrapedGame

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_DATE_SHORT_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})")
_TIME_RE = re.compile(r"(\d{2}):(\d{2})")
_VENUE_ID_RE = re.compile(r"/id/([^/?#]+)")

# Platzhalter-Bezeichnungen, die keinen echten Spielgegner darstellen.
# Solche Einträge tauchen bei "Spielfrei"-Runden im Spielplan auf und
# dürfen nicht als Belegungsslots erscheinen.
_SPIELFREI_MARKERS: frozenset[str] = frozenset({"spielfrei", "bye"})
_CANCELLED_GAME_MARKERS: frozenset[str] = frozenset(
    {"absetzung", "abgesetzt", "abgesagt", "ausgefallen", "annulliert"}
)


def _is_placeholder_team(name: str) -> bool:
    """Prüft, ob ein Mannschaftsname ein Platzhalter ist (z.B. 'spielfrei').

    Platzhalter entstehen bei spielfreien Runden und repräsentieren keinen
    echten Spielgegner.  Solche Zeilen müssen beim Parsen übersprungen werden.
    """
    return name.strip().lower() in _SPIELFREI_MARKERS


def _is_cancelled_game_status(text: str) -> bool:
    """Prüft, ob ein Match-Status auf ein abgesetztes Spiel hinweist."""
    normalized = text.strip().lower()
    return bool(normalized and normalized in _CANCELLED_GAME_MARKERS)


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
    """Normalisiert einen Ortsnamen für den Vergleich.

    Wandelt in Kleinbuchstaben um, entfernt führende/nachfolgende Leerzeichen
    und reduziert mehrfache Leerzeichen auf eines.
    """
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

    # Patterns einmalig kompilieren
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
            # 1. ID-Vergleich
            if getattr(vc, "id", "") and game_venue_id == vc.id:
                match_found = True
                break

            # 2. Alias-Vergleich (normalisiert)
            for alias in getattr(vc, "aliases", []):
                if _normalize_venue_name(alias) == game_venue_norm:
                    match_found = True
                    break
            if match_found:
                break

            # 3. Regex-Muster-Vergleich
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


def _safe_text(el: Optional[Tag]) -> str:
    """Gibt den Text eines Elements zurück oder einen leeren String."""
    return el.get_text(strip=True).replace("\u200b", "") if el else ""


def _parse_german_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Parst ein deutsches Datum und eine Uhrzeit zu einem datetime-Objekt."""
    m = _DATE_RE.search(date_str)
    if not m:
        m_short = _DATE_SHORT_RE.search(date_str)
        if m_short:
            day, month, year = (
                int(m_short.group(1)),
                int(m_short.group(2)),
                2000 + int(m_short.group(3)),
            )
        else:
            return None
    else:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    t = _TIME_RE.search(time_str or "")
    hour = int(t.group(1)) if t else 0
    minute = int(t.group(2)) if t else 0
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def _normalize_german_date(date_str: str) -> str:
    """Normalisiert deutsche Datumsangaben auf dd.mm.yyyy."""
    parsed = _parse_german_datetime(date_str, "")
    if not parsed:
        return date_str
    return parsed.strftime("%d.%m.%Y")


class FussballDeScraper:
    """Scrapt Spielplandaten direkt von fussball.de."""

    def __init__(self, cfg: ScraperConfig | None = None) -> None:
        self._cfg = cfg or ScraperConfig()
        self._session = requests.Session()
        self._game_detail_cache: dict[str, dict[str, str]] = {}
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
    # Öffentliche Methoden – Club Matchplan (Primary)
    # ------------------------------------------------------------------

    def scrape_club_matchplan(
        self,
        club_id: str,
        season: str | None = None,
        limit: int = 100,
    ) -> list[ScrapedGame]:
        """Scrapt alle Spiele eines Vereins über ajax.club.matchplan.

        Dies ist die primäre Scraping-Methode, da sie auf der strukturierten
        AJAX-API basiert und stabiler ist als HTML-Parsing von Sportstätten-Seiten.

        Args:
            club_id: ID des Vereins (aus der fussball.de-URL).
            season: Saison-Code (z.B. "2526" für 2025/26). Optional.
            limit: Maximale Anzahl der zu ladenden Spiele (für Paginierung).

        Returns:
            Liste der gefundenen Spiele als ScrapedGame-Objekte.

        Note:
            Die Spiele enthalten möglicherweise mehrere Sportstätten.
            Verwende anschließend Filterung nach venue_id, wenn nur
            bestimmte Plätze relevant sind.
        """
        url = f"{self._cfg.fussball_de_base}/ajax.club.matchplan"
        scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.debug("Scraping club matchplan: %s (season=%s)", club_id, season)

        params = {"id": club_id}
        if season:
            params["saisonId"] = season

        all_games: list[ScrapedGame] = []
        offset = 0
        page = 1

        while len(all_games) < limit:
            try:
                # Pagination via loadmore parameter
                if offset > 0:
                    params["loadmore"] = str(offset)

                logger.debug("Fetching page %d (offset %d)", page, offset)
                response = self._session.get(
                    url, params=params, timeout=self._cfg.timeout_seconds
                )
                response.raise_for_status()

                # Parse JSON or HTML response depending on what the API returns
                content_type = response.headers.get("content-type", "")

                if "application/json" in content_type:
                    # JSON response - parse directly
                    games = self._parse_matchplan_json(
                        response.json(), scraped_at
                    )
                else:
                    # HTML fragment response - parse as HTML
                    soup = BeautifulSoup(response.text, "html.parser")
                    games = self._parse_matchplan_html(soup, scraped_at)

                if not games:
                    logger.debug("No more games found, stopping pagination")
                    break

                all_games.extend(games)
                logger.debug("Page %d: %d games found", page, len(games))

                # Check if we should continue pagination
                # Many AJAX endpoints return empty or fewer results on last page
                if len(games) < 20:  # Typical page size
                    break

                offset += len(games)
                page += 1

            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "Failed to fetch page %d: %s", page, exc, exc_info=True
                )
                break

        logger.info(
            "Club %s: %d Spiel(e) gefunden über matchplan API", club_id, len(all_games)
        )
        return all_games[:limit]

    # ------------------------------------------------------------------
    # Öffentliche Methoden – Venue-based (Deprecated/Fallback)
    # ------------------------------------------------------------------

    def scrape_venue_games(self, venue_id: str) -> list[ScrapedGame]:
        """Scrapt alle Spiele für eine Sportstätte von fussball.de.

        DEPRECATED: Diese Methode scrapt die HTML-Seiten von Sportstätten
        (sportstaette/-/id/...), die jedoch keine stabilen Match-Rows mehr
        anzeigen. Die HTML-Struktur ändert sich häufig und ist nicht für
        maschinelles Auslesen gedacht.

        Bevorzuge stattdessen scrape_club_matchplan() und filtere anschließend
        nach venue_id.

        Args:
            venue_id: ID der Sportstätte (aus der fussball.de-URL).

        Returns:
            Liste der gefundenen Spiele als ScrapedGame-Objekte.
        """
        logger.warning(
            "scrape_venue_games() is deprecated. Use scrape_club_matchplan() instead."
        )
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
    # Interne Parser – Club Matchplan
    # ------------------------------------------------------------------

    def _parse_matchplan_json(
        self, data: dict, scraped_at: str
    ) -> list[ScrapedGame]:
        """Parst JSON-Response von ajax.club.matchplan."""
        games: list[ScrapedGame] = []

        # The structure might vary, but typically contains a games/matches array
        matches = data.get("matches", data.get("games", []))

        for match in matches:
            # Extract venue information
            venue_info = match.get("venue", {})
            venue_id = venue_info.get("id", "")
            venue_name = venue_info.get("name", "")

            # Extract date and time
            date_str = match.get("date", "")
            time_str = match.get("time", "")

            # Extract teams
            home_team = match.get("homeTeam", {}).get("name", "")
            guest_team = match.get("awayTeam", {}).get("name", "")

            # Extract competition
            competition = match.get("competition", {}).get("name", "")
            status_candidates = [
                str(match.get("status", "")),
                str(match.get("result", "")),
                str(match.get("score", "")),
                str(match.get("matchStatus", "")),
            ]

            if not date_str or not home_team:
                continue

            # Spielfrei-Einträge überspringen (kein echter Spielgegner)
            if _is_placeholder_team(home_team) or _is_placeholder_team(guest_team):
                logger.debug(
                    "Überspringe Spielfrei-Eintrag (JSON): %r vs %r (%s)",
                    home_team, guest_team, date_str,
                )
                continue

            if any(_is_cancelled_game_status(candidate) for candidate in status_candidates):
                logger.debug(
                    "Überspringe abgesetztes Spiel (JSON): %r vs %r (%s)",
                    home_team, guest_team, date_str,
                )
                continue

            start_dt = _parse_german_datetime(date_str, time_str)
            if not start_dt:
                continue

            games.append(
                ScrapedGame(
                    venue_id=venue_id,
                    venue_name=venue_name,
                    date=date_str,
                    time=time_str,
                    home_team=home_team,
                    guest_team=guest_team,
                    competition=competition,
                    start_date=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    scraped_at=scraped_at,
                )
            )

        return games

    def _parse_matchplan_html(
        self, soup: BeautifulSoup, scraped_at: str
    ) -> list[ScrapedGame]:
        """Parst HTML-Fragment von ajax.club.matchplan.

        Das AJAX-Endpoint gibt oft HTML-Fragmente zurück statt JSON.
        Diese Methode parst die typischen HTML-Strukturen.
        """
        games: list[ScrapedGame] = []

        def _next_tag_sibling(row: Tag) -> Optional[Tag]:
            sibling = row.next_sibling
            while sibling is not None and not isinstance(sibling, Tag):
                sibling = sibling.next_sibling
            return sibling if isinstance(sibling, Tag) else None

        tbody_rows = soup.select("table.table-striped tbody tr")
        rows = tbody_rows or soup.select(".match-row, .game-row, .matchplan-row")

        current_date_text = ""
        current_time_text = ""
        current_competition = ""

        for row in rows:
            row_classes = set(row.get("class", []))

            if "row-headline" in row_classes or "row-venue" in row_classes:
                continue

            if "row-competition" in row_classes:
                # fussball.de renders match metadata on a separate row.
                date_cell = row.select_one(".column-date, .date, .match-date")
                competition_cell = row.select_one(
                    ".column-team, .competition, .league"
                )
                date_time_text = _safe_text(date_cell)
                current_date_text = ""
                current_time_text = ""

                date_match = _DATE_RE.search(date_time_text)
                if date_match:
                    current_date_text = date_match.group(0)
                else:
                    date_match_short = _DATE_SHORT_RE.search(date_time_text)
                    if date_match_short:
                        current_date_text = date_match_short.group(0)

                time_match = _TIME_RE.search(date_time_text)
                if time_match:
                    current_time_text = time_match.group(0)

                current_competition = _safe_text(competition_cell)
                continue

            # Extract venue - might be in data attributes, nested elements,
            # or in a following .row-venue row.
            venue_id = row.get("data-venue-id", "")
            if not venue_id:
                venue_elem = row.select_one("[data-venue-id]")
                venue_id = venue_elem.get("data-venue-id", "") if venue_elem else ""

            venue_name_elem = row.select_one(".venue, .venue-name, [data-venue-name]")
            if venue_name_elem:
                venue_name = _safe_text(venue_name_elem) or venue_name_elem.get(
                    "data-venue-name", ""
                )
            else:
                next_row = _next_tag_sibling(row)
                if next_row and "row-venue" in set(next_row.get("class", [])):
                    venue_name = _safe_text(next_row.select_one("td[colspan='3']")) or _safe_text(next_row)
                else:
                    venue_name = ""

            status_text = _safe_text(
                row.select_one(".column-score, .column-result, .score, .result, .match-result")
            )

            game_link = row.select_one("a[href*='/spiel/']")
            game_url = (
                urljoin(self._cfg.fussball_de_base, game_link.get("href", ""))
                if game_link
                else ""
            )
            detail: dict[str, str] = {}
            if game_url and (not venue_name or not status_text):
                detail = self._fetch_game_detail(game_url)
            if not venue_name and detail:
                venue_name = detail.get("venue_name", "")
            if not status_text and detail:
                status_text = detail.get("status_text", "")

            # Extract date and time
            date_text = _safe_text(row.select_one(".date, .match-date"))
            time_text = _safe_text(row.select_one(".time, .match-time"))
            if not date_text:
                date_text = current_date_text
            if not time_text:
                time_text = current_time_text

            # Extract teams
            home_team = _safe_text(row.select_one(".home-team, .team-home"))
            guest_team = _safe_text(row.select_one(".guest-team, .team-guest"))

            if not home_team:
                club_cells = row.select("td.column-club")
                if len(club_cells) >= 1:
                    home_team = _safe_text(club_cells[0].select_one(".club-name")) or _safe_text(club_cells[0])
                if len(club_cells) >= 2:
                    guest_team = _safe_text(club_cells[1].select_one(".club-name, .info-text")) or _safe_text(club_cells[1])

            if not home_team:
                home_team = _safe_text(row.select_one("td:nth-child(3)"))
            if not guest_team:
                guest_team = _safe_text(row.select_one("td:nth-child(5)"))

            if _is_cancelled_game_status(status_text):
                logger.debug(
                    "Überspringe abgesetztes Spiel (HTML): %r vs %r (%s)",
                    home_team, guest_team, date_text or current_date_text,
                )
                continue

            # Extract competition
            competition = _safe_text(row.select_one(".competition, .league"))
            if not competition:
                competition = current_competition
            if not competition:
                competition = _safe_text(row.select_one("td:nth-child(6)"))

            if not date_text or not home_team:
                continue

            date_text = _normalize_german_date(date_text)

            # Spielfrei-Einträge überspringen (kein echter Spielgegner)
            if _is_placeholder_team(home_team) or _is_placeholder_team(guest_team):
                logger.debug(
                    "Überspringe Spielfrei-Eintrag (HTML): %r vs %r (%s)",
                    home_team, guest_team, date_text,
                )
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

    def _fetch_game_detail(self, game_url: str) -> dict[str, str]:
        """Lädt ergänzende Spieldetails von der Detailseite.

        Aktuell wird nur die Spielstätte benötigt. Die Ergebnisse werden je URL
        gecacht, damit derselbe Link bei mehrfacher Verwendung nicht erneut
        angefragt wird.
        """
        if not game_url:
            return {}

        cached = self._game_detail_cache.get(game_url)
        if cached is not None:
            return cached

        try:
            response = self._session.get(
                game_url, timeout=self._cfg.timeout_seconds
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.debug(
                "Failed to fetch game detail page: %s", game_url, exc_info=True
            )
            self._game_detail_cache[game_url] = {}
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        venue_name = ""
        for selector in (
            "a.location",
            ".location",
            ".match-place .location",
            ".game-place .location",
        ):
            node = soup.select_one(selector)
            text = _safe_text(node)
            if text:
                venue_name = text
                break

        status_text = ""
        for selector in (
            ".result .info-text",
            ".result",
            ".match-result .info-text",
            ".match-result",
            ".score .info-text",
        ):
            node = soup.select_one(selector)
            text = _safe_text(node)
            if text:
                status_text = text
                break

        detail = {"venue_name": venue_name, "status_text": status_text}
        self._game_detail_cache[game_url] = detail
        return detail

    # ------------------------------------------------------------------
    # Interne Parser – Venue Pages (Deprecated)
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

            # Spielfrei-Einträge überspringen (kein echter Spielgegner)
            if _is_placeholder_team(home_team) or _is_placeholder_team(guest_team):
                logger.debug(
                    "Überspringe Spielfrei-Eintrag (Tabelle): %r vs %r (%s)",
                    home_team, guest_team, date_text,
                )
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

            # Spielfrei-Einträge überspringen (kein echter Spielgegner)
            if _is_placeholder_team(home_team) or _is_placeholder_team(guest_team):
                logger.debug(
                    "Überspringe Spielfrei-Eintrag (Fixture): %r vs %r (%s)",
                    home_team, guest_team, date_text,
                )
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
