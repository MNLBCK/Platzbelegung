"""CLI-Einstiegspunkt für die Platzbelegungs-Übersicht.

Subcommands
-----------
scrape  – Sportstätten direkt von fussball.de scrapen und Daten speichern.
html    – Statische HTML-Datei aus dem letzten Snapshot generieren.
show    – Platzbelegung aus dem letzten Snapshot im Terminal anzeigen.
legacy  – (Abwärtskompatibel) Daten über die lokale fussball.de REST-API abrufen.

Wird kein Subcommand angegeben, verhält sich das Tool wie bisher (legacy).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import requests
from rich.console import Console

from platzbelegung import config as cfg
from platzbelegung.config import load_config

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subcommand: scrape
# ---------------------------------------------------------------------------

def _cmd_scrape(args: argparse.Namespace, app_cfg, console: Console) -> int:
    """Scrapt konfigurierte Sportstätten und speichert einen JSON-Snapshot.

    Verwendet primär die club matchplan API (ajax.club.matchplan) und filtert
    anschließend nach konfigurierten Sportstätten. Falls --venue-id angegeben
    wird, wird der alte venue-basierte Scraper als Fallback verwendet.
    """
    from platzbelegung.scraper import FussballDeScraper, filter_games_by_venue_configs
    from platzbelegung.storage import save_snapshot

    # Check if user wants to use old venue-based scraping
    use_venue_scraping = args.venue_id is not None and len(args.venue_id) > 0

    scraper = FussballDeScraper(app_cfg.scraper)
    all_games = []

    if use_venue_scraping:
        # Legacy mode: scrape individual venues (deprecated)
        venue_ids: list[str] = args.venue_id
        console.print(
            "[yellow]Hinweis:[/yellow] Verwende venue-basiertes Scraping (deprecated). "
            "Dies ist weniger stabil als club-basiertes Scraping."
        )
        console.print()

        for vid in venue_ids:
            console.print(f"  Scraping venue [cyan]{vid}[/cyan] …")
            try:
                games = scraper.scrape_venue_games(vid)
                console.print(f"    → {len(games)} Spiel(e) gefunden")
                all_games.extend(games)
            except requests.exceptions.RequestException as exc:
                console.print(f"    [red]Netzwerkfehler:[/red] {exc}")
                logger.debug("Scraping error for %s", vid, exc_info=True)
            except Exception as exc:  # noqa: BLE001 – unexpected errors logged + shown
                console.print(f"    [red]Fehler:[/red] {exc}")
                logger.debug("Unexpected error scraping %s", vid, exc_info=True)
    else:
        # Primary mode: scrape club matchplan and filter by venues
        if not app_cfg.club_id:
            console.print(
                "[red]Fehler:[/red] Keine club.id in config.yaml konfiguriert. "
                "Bitte Vereins-ID eintragen oder --venue-id verwenden."
            )
            return 1

        console.print(
            f"Scraping club matchplan: [cyan]{app_cfg.club_name or app_cfg.club_id}[/cyan]"
        )
        console.print()

        try:
            all_games = scraper.scrape_club_matchplan(
                club_id=app_cfg.club_id,
                season=app_cfg.season,
            )
            console.print(f"  → {len(all_games)} Spiel(e) vom Verein gefunden")

            # Filter by configured venues if any
            if app_cfg.venues:
                console.print(
                    f"  Filtere nach {len(app_cfg.venues)} Sportstätte(n) …"
                )
                all_games = filter_games_by_venue_configs(all_games, app_cfg.venues)
                console.print(
                    f"  → {len(all_games)} Spiel(e) auf konfigurierten Plätzen"
                )

        except requests.exceptions.RequestException as exc:
            console.print(f"[red]Netzwerkfehler:[/red] {exc}")
            logger.debug("Scraping error for club %s", app_cfg.club_id, exc_info=True)
            return 1
        except Exception as exc:  # noqa: BLE001 – unexpected errors logged + shown
            console.print(f"[red]Fehler:[/red] {exc}")
            logger.debug(
                "Unexpected error scraping club %s", app_cfg.club_id, exc_info=True
            )
            return 1

    # Collect venue IDs for metadata
    if use_venue_scraping:
        venue_ids_meta = args.venue_id
    else:
        venue_ids_meta = [v.id for v in app_cfg.venues] if app_cfg.venues else []

    config_meta = {
        "club_id": app_cfg.club_id,
        "club_name": app_cfg.club_name,
        "season": app_cfg.season,
        "venues": venue_ids_meta,
    }

    snap_path = save_snapshot(
        all_games,
        config_meta,
        snapshots_dir=app_cfg.output.snapshots_dir,
    )
    console.print()
    console.print(
        f"[bold green]✓[/bold green] Snapshot gespeichert: "
        f"[dim]{snap_path}[/dim]"
    )
    console.print(
        f"[bold green]✓[/bold green] Aktuellster Snapshot: "
        f"[dim]{Path(app_cfg.output.data_dir) / 'latest.json'}[/dim]"
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: html
# ---------------------------------------------------------------------------

def _cmd_html(args: argparse.Namespace, app_cfg, console: Console) -> int:
    """Generiert eine statische HTML-Datei aus dem letzten Snapshot."""
    from platzbelegung.parser import scraped_games_to_occupancy
    from platzbelegung.render_html import render_html
    from platzbelegung.storage import games_from_snapshot, load_latest_snapshot

    snapshot = load_latest_snapshot(app_cfg.output.data_dir)
    if snapshot is None:
        console.print(
            "[red]Kein Snapshot gefunden.[/red] "
            "Bitte zuerst [bold]platzbelegung scrape[/bold] ausführen."
        )
        return 1

    games = games_from_snapshot(snapshot)
    slots = scraped_games_to_occupancy(
        games,
        preparation_buffer_minutes=app_cfg.scraper.preparation_buffer_minutes,
        default_duration_minutes=app_cfg.scraper.default_game_duration_minutes,
        game_durations=app_cfg.scraper.game_durations,
    )

    output_path = Path(args.output or app_cfg.output.html_file)
    render_html(
        slots,
        output_path=output_path,
        generated_at=snapshot.get("generated_at", ""),
    )

    console.print(
        f"[bold green]✓[/bold green] HTML-Datei erstellt: [dim]{output_path}[/dim]"
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: show
# ---------------------------------------------------------------------------

def _cmd_show(_args: argparse.Namespace, app_cfg, console: Console) -> int:
    """Zeigt die Platzbelegung aus dem letzten Snapshot im Terminal an."""
    from platzbelegung.display import display_occupancy
    from platzbelegung.parser import scraped_games_to_occupancy
    from platzbelegung.storage import games_from_snapshot, load_latest_snapshot

    snapshot = load_latest_snapshot(app_cfg.output.data_dir)
    if snapshot is None:
        console.print(
            "[red]Kein Snapshot gefunden.[/red] "
            "Bitte zuerst [bold]platzbelegung scrape[/bold] ausführen."
        )
        return 1

    games = games_from_snapshot(snapshot)
    slots = scraped_games_to_occupancy(
        games,
        preparation_buffer_minutes=app_cfg.scraper.preparation_buffer_minutes,
        default_duration_minutes=app_cfg.scraper.default_game_duration_minutes,
        game_durations=app_cfg.scraper.game_durations,
    )

    generated_at = snapshot.get("generated_at", "")
    console.print(f"[bold]Platzbelegung[/bold]  [dim]Stand: {generated_at}[/dim]")
    console.print()
    display_occupancy(slots, console=console)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: legacy (original iste2-API-basierter Pfad)
# ---------------------------------------------------------------------------

def _cmd_legacy(args: argparse.Namespace, app_cfg, console: Console) -> int:
    """Ruft Daten über die lokale fussball.de REST-API ab (legacy)."""
    from platzbelegung.api_client import ApiError, FussballDeApiClient
    from platzbelegung.display import display_occupancy
    from platzbelegung.parser import games_to_occupancy

    club_id = args.club_id or app_cfg.club_id
    api_url = args.api_url or cfg.API_BASE_URL
    season = args.season or app_cfg.season

    client = FussballDeApiClient(base_url=api_url)
    start, end = cfg.get_date_range()

    console.print(
        f"[bold green]Platzbelegung – Verein:[/bold green] {club_id}  "
        f"[dim]Zeitraum: {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}[/dim]"
    )
    console.print()

    try:
        teams = client.get_teams(club_id, season)
        console.print(f"[bold]Mannschaften ({len(teams)}):[/bold]")
        for team in teams:
            console.print(f"  • {team.name} [dim]({team.kind or '–'})[/dim]")
        console.print()
    except ApiError as exc:
        console.print(f"[red]Fehler beim Abrufen der Mannschaften:[/red] {exc}")
        return 1

    try:
        games = client.get_club_games(club_id, start, end, home_only=True)
        console.print(f"[dim]Heimspiele im Zeitraum: {len(games)}[/dim]")
        console.print()
    except ApiError as exc:
        console.print(f"[red]Fehler beim Abrufen der Spiele:[/red] {exc}")
        return 1

    team_kinds = {g.home_side.kind for g in games if g.home_side.kind}
    game_durations: dict[str, int] = {}
    for kind in team_kinds:
        try:
            duration = client.get_game_duration(kind)
            game_durations[kind] = duration
            logger.debug("Spieldauer %s: %d min", kind, duration)
        except ApiError:
            logger.warning(
                "Spieldauer für '%s' nicht verfügbar, verwende %d min.", kind, 90
            )
            game_durations[kind] = 90

    slots = games_to_occupancy(games, club_id, game_durations)
    display_occupancy(slots, console=console)
    return 0


# ---------------------------------------------------------------------------
# Argument-Parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="platzbelegung",
        description="Fußball-Platzbelegungs-Übersicht basierend auf fussball.de-Daten",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Detaillierte Ausgabe (Debug-Logging)",
    )

    sub = p.add_subparsers(dest="command")

    # scrape
    p_scrape = sub.add_parser(
        "scrape",
        help="Vereins-Matchplan scrapen und Snapshot speichern (primär via ajax.club.matchplan)",
    )
    p_scrape.add_argument(
        "--venue-id",
        metavar="ID",
        nargs="+",
        help="[DEPRECATED] Sportstätten-ID(s) direkt scrapen (verwendet alten HTML-Parser)",
    )

    # html
    p_html = sub.add_parser("html", help="HTML-Datei aus letztem Snapshot generieren")
    p_html.add_argument(
        "--output", "-o",
        metavar="PFAD",
        default=None,
        help="Ausgabepfad der HTML-Datei (Standard: aus config.yaml)",
    )

    # show
    sub.add_parser("show", help="Platzbelegung aus letztem Snapshot im Terminal anzeigen")

    # legacy
    p_legacy = sub.add_parser(
        "legacy",
        help="Daten über die lokale fussball.de REST-API abrufen (iste2-API)",
    )
    p_legacy.add_argument(
        "--club-id", default=None, metavar="ID",
        help=f"Vereins-ID (Standard: {cfg.CLUB_ID})",
    )
    p_legacy.add_argument(
        "--api-url", default=None, metavar="URL",
        help=f"Basis-URL der fussball.de REST API (Standard: {cfg.API_BASE_URL})",
    )
    p_legacy.add_argument(
        "--season", default=None, metavar="SAISON",
        help=f"Saison-Code, z.B. '2526' für 2025/26 (Standard: {cfg.SEASON})",
    )

    return p


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console = Console()
    app_cfg = load_config()

    command = args.command
    if command == "scrape":
        return _cmd_scrape(args, app_cfg, console)
    if command == "html":
        return _cmd_html(args, app_cfg, console)
    if command == "show":
        return _cmd_show(args, app_cfg, console)
    if command == "legacy":
        return _cmd_legacy(args, app_cfg, console)

    # Kein Subcommand: Hilfe anzeigen
    _build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

