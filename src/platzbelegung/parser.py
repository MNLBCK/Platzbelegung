"""Logik: Spiele → Platzbelegung umwandeln."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import DefaultDict

from platzbelegung.models import Game, OccupancySlot, Venue

# Puffer in Minuten, der vor dem Anstoß für Vorbereitung eingeplant wird
PREPARATION_BUFFER_MINUTES: int = 15

# Standard-Spieldauer, falls kein Wert für die Mannschaftsart bekannt ist
DEFAULT_DURATION_MINUTES: int = 90


def extract_venue(address: str) -> Venue:
    """Extrahiert den Spielort aus dem Adressfeld eines Spiels.

    Das Format ist typischerweise:
        "Platzname, Sportanlage, Straße, PLZ Ort"
    oder auch nur:
        "Straße, PLZ Ort"

    Die erste Komponente wird als Platzname verwendet, der Rest als
    Adresse.  Wenn nur eine Komponente vorhanden ist, wird sie sowohl
    als Name als auch als Adresse verwendet.
    """
    if not address:
        return Venue(name="Unbekannt", address="")

    parts = [p.strip() for p in address.split(",")]
    if len(parts) == 1:
        return Venue(name=parts[0], address=parts[0])

    name = parts[0]
    full_address = ", ".join(parts[1:])
    return Venue(name=name, address=full_address)


def games_to_occupancy(
    games: list[Game],
    club_id: str,
    game_durations: dict[str, int],
) -> list[OccupancySlot]:
    """Wandelt eine Liste von Spielen in Belegungsslots um.

    Nur Heimspiele des angegebenen Vereins erzeugen einen Belegungsslot.

    Args:
        games: Liste aller Spiele.
        club_id: Die Vereins-ID, für die die Belegung berechnet werden soll.
        game_durations: Zuordnung Mannschaftsart → Spieldauer in Minuten.

    Returns:
        Liste von OccupancySlot-Objekten, sortiert nach Datum und Uhrzeit.
    """
    slots: list[OccupancySlot] = []

    for game in games:
        # Nur Heimspiele berücksichtigen
        if game.home_side.club_id != club_id:
            continue

        team_kind = game.home_side.kind
        duration = game_durations.get(team_kind, DEFAULT_DURATION_MINUTES)

        venue = extract_venue(game.address)

        kick_off = game.kick_off
        start_time = (kick_off - timedelta(minutes=PREPARATION_BUFFER_MINUTES)).time()
        end_time = (kick_off + timedelta(minutes=duration)).time()

        slot = OccupancySlot(
            venue=venue,
            date=kick_off.date(),
            start_time=start_time,
            end_time=end_time,
            team_name=game.home_side.name,
            team_kind=team_kind,
            opponent=game.away_side.name,
            league=game.league,
            is_home_game=True,
        )
        slots.append(slot)

    slots.sort(key=lambda s: (s.date, s.start_time))
    return slots


def group_by_venue(
    slots: list[OccupancySlot],
) -> dict[Venue, list[OccupancySlot]]:
    """Gruppiert Belegungsslots nach Sportstätte."""
    grouped: DefaultDict[Venue, list[OccupancySlot]] = defaultdict(list)
    for slot in slots:
        grouped[slot.venue].append(slot)
    return dict(grouped)


def group_by_date(
    slots: list[OccupancySlot],
) -> dict[date, list[OccupancySlot]]:
    """Gruppiert Belegungsslots nach Datum."""
    grouped: DefaultDict[date, list[OccupancySlot]] = defaultdict(list)
    for slot in slots:
        grouped[slot.date].append(slot)
    return dict(grouped)
