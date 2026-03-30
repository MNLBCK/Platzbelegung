"""CLI-Einstiegspunkt für die Platzbelegungs-Übersicht."""

from __future__ import annotations

import argparse
import logging
import sys

from rich.console import Console

from platzbelegung import config as cfg
from platzbelegung.api_client import ApiError, FussballDeApiClient
from platzbelegung.display import display_occupancy
from platzbelegung.parser import games_to_occupancy

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="platzbelegung",
        description="Fußball-Platzbelegungs-Übersicht basierend auf fussball.de-Daten",
    )
    p.add_argument(
        "--club-id",
        default=None,
        metavar="ID",
        help=f"Vereins-ID (Standard: {cfg.CLUB_ID})",
    )
    p.add_argument(
        "--api-url",
        default=None,
        metavar="URL",
        help=f"Basis-URL der fussball.de REST API (Standard: {cfg.API_BASE_URL})",
    )
    p.add_argument(
        "--season",
        default=None,
        metavar="SAISON",
        help=f"Saison-Code, z.B. '2526' für 2025/26 (Standard: {cfg.SEASON})",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Detaillierte Ausgabe (Debug-Logging)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    club_id = args.club_id or cfg.CLUB_ID
    api_url = args.api_url or cfg.API_BASE_URL
    season = args.season or cfg.SEASON

    console = Console()
    client = FussballDeApiClient(base_url=api_url)

    start, end = cfg.get_date_range()

    console.print(
        f"[bold green]Platzbelegung – Verein:[/bold green] {club_id}  "
        f"[dim]Zeitraum: {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}[/dim]"
    )
    console.print()

    # 1. Mannschaften abrufen und ausgeben
    try:
        teams = client.get_teams(club_id, season)
        console.print(f"[bold]Mannschaften ({len(teams)}):[/bold]")
        for team in teams:
            console.print(f"  • {team.name} [dim]({team.kind or '–'})[/dim]")
        console.print()
    except ApiError as exc:
        console.print(f"[red]Fehler beim Abrufen der Mannschaften:[/red] {exc}")
        return 1

    # 2. Heimspiele im Zeitraum abrufen
    try:
        games = client.get_club_games(club_id, start, end, home_only=True)
        console.print(f"[dim]Heimspiele im Zeitraum: {len(games)}[/dim]")
        console.print()
    except ApiError as exc:
        console.print(f"[red]Fehler beim Abrufen der Spiele:[/red] {exc}")
        return 1

    # 3. Spieldauern für die vorkommenden Mannschaftsarten abrufen
    team_kinds = {g.home_side.kind for g in games if g.home_side.kind}
    game_durations: dict[str, int] = {}
    for kind in team_kinds:
        try:
            duration = client.get_game_duration(kind)
            game_durations[kind] = duration
            logger.debug("Spieldauer %s: %d min", kind, duration)
        except ApiError:
            logger.warning(
                "Spieldauer für '%s' nicht verfügbar, verwende %d min.",
                kind,
                90,
            )
            game_durations[kind] = 90

    # 4. Spiele → OccupancySlots
    slots = games_to_occupancy(games, club_id, game_durations)

    # 5. Ausgabe
    display_occupancy(slots, console=console)

    return 0


if __name__ == "__main__":
    sys.exit(main())
