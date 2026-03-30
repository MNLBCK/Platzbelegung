"""Tabellarische Ausgabe der Platzbelegung mit der rich-Bibliothek."""

from __future__ import annotations

import locale
from datetime import date

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from platzbelegung.models import OccupancySlot, Venue
from platzbelegung.parser import group_by_date, group_by_venue

_WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]

_MONTHS_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _format_date_de(d: date) -> str:
    weekday = _WEEKDAYS_DE[d.weekday()]
    month = _MONTHS_DE[d.month]
    return f"{weekday}, {d.day:02d}. {month} {d.year}"


def _format_time(t) -> str:
    return t.strftime("%H:%M")


def display_occupancy(
    slots: list[OccupancySlot],
    console: Console | None = None,
) -> None:
    """Gibt die Platzbelegung gruppiert nach Sportstätte und Datum aus.

    Args:
        slots: Alle zu zeigenden Belegungsslots.
        console: Optional – eine bestehende rich Console. Wird keine
                 übergeben, wird eine neue erstellt.
    """
    if console is None:
        console = Console()

    if not slots:
        console.print("[yellow]Keine Belegungen im gewählten Zeitraum gefunden.[/yellow]")
        return

    by_venue = group_by_venue(slots)

    for venue, venue_slots in sorted(by_venue.items(), key=lambda kv: str(kv[0])):
        _print_venue_section(console, venue, venue_slots)


def _print_venue_section(
    console: Console,
    venue: Venue,
    slots: list[OccupancySlot],
) -> None:
    console.print()
    console.print(Rule(f"📍 {venue}", style="bold cyan"))
    console.print()

    by_date = group_by_date(slots)

    for d, day_slots in sorted(by_date.items()):
        console.print(f"  📅 [bold]{_format_date_de(d)}[/bold]")
        console.print()
        _print_day_table(console, day_slots)
        console.print()


def _print_day_table(
    console: Console,
    slots: list[OccupancySlot],
) -> None:
    table = Table(
        show_header=True,
        header_style="bold",
        box=None,
        padding=(0, 1),
        expand=False,
    )

    table.add_column("Von", style="cyan", no_wrap=True)
    table.add_column("Bis", style="cyan", no_wrap=True)
    table.add_column("Mannschaft", style="white")
    table.add_column("Art", style="dim")
    table.add_column("Gegner", style="white")
    table.add_column("Liga", style="dim")

    sorted_slots = sorted(slots, key=lambda s: s.start_time)
    for slot in sorted_slots:
        table.add_row(
            _format_time(slot.start_time),
            _format_time(slot.end_time),
            slot.team_name,
            slot.team_kind,
            slot.opponent,
            slot.league,
        )

    console.print(table)
