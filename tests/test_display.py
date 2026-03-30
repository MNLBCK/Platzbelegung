"""Smoke-Tests für display.py – stellt sicher, dass keine Exceptions geworfen werden."""

from __future__ import annotations

from datetime import date, time

from rich.console import Console

from platzbelegung.display import display_occupancy
from platzbelegung.models import OccupancySlot, Venue


def _make_console() -> Console:
    """Erstellt eine Console, die in einen String schreibt."""
    return Console(force_terminal=False, no_color=True)


def _make_slots() -> list[OccupancySlot]:
    venue_a = Venue(name="Kunstrasenplatz", address="Sportanlage Hochberg, Hauptstr. 1, 70000 Stuttgart")
    venue_b = Venue(name="Rasenplatz", address="Nebenstraße 5, 70001 Stuttgart")
    return [
        OccupancySlot(
            venue=venue_a,
            date=date(2026, 4, 5),
            start_time=time(10, 45),
            end_time=time(12, 15),
            team_name="Herren",
            team_kind="Herren",
            opponent="FC Muster",
            league="Kreisliga A",
        ),
        OccupancySlot(
            venue=venue_a,
            date=date(2026, 4, 5),
            start_time=time(12, 45),
            end_time=time(14, 15),
            team_name="Herren II",
            team_kind="Herren",
            opponent="SV Beispiel",
            league="Kreisliga B",
        ),
        OccupancySlot(
            venue=venue_b,
            date=date(2026, 4, 6),
            start_time=time(10, 45),
            end_time=time(11, 55),
            team_name="D-Jugend",
            team_kind="D-Junioren",
            opponent="TSV Test",
            league="Kreisliga D",
        ),
    ]


def test_display_no_exception():
    """display_occupancy darf keine Exception werfen."""
    console = _make_console()
    display_occupancy(_make_slots(), console=console)


def test_display_empty_no_exception():
    """display_occupancy mit leerer Liste darf keine Exception werfen."""
    console = _make_console()
    display_occupancy([], console=console)


def test_display_contains_venue_name(capsys):
    """Die Ausgabe enthält den Sportstätten-Namen."""
    import io

    from rich.console import Console

    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=False, no_color=True)
    display_occupancy(_make_slots(), console=console)
    output = string_io.getvalue()
    assert "Kunstrasenplatz" in output
    assert "Rasenplatz" in output


def test_display_contains_team_names(capsys):
    """Die Ausgabe enthält die Mannschaftsnamen."""
    import io

    from rich.console import Console

    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=False, no_color=True)
    display_occupancy(_make_slots(), console=console)
    output = string_io.getvalue()
    assert "Herren" in output
    assert "D-Jugend" in output
