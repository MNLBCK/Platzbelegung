"""Logik: Spiele → Platzbelegung umwandeln."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime as _dt, timedelta
from typing import DefaultDict

from platzbelegung.models import Game, OccupancySlot, ScrapedGame, Venue

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
        # Nur Heimspiele berücksichtigen: Auswärtsspiele erzeugen keinen Slot,
        # da der eigene Platz dabei nicht belegt wird.
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


def scraped_games_to_occupancy(
    games: list[ScrapedGame],
    preparation_buffer_minutes: int = 15,
    default_duration_minutes: int = 90,
    game_durations: dict[str, int] | None = None,
) -> list[OccupancySlot]:
    """Wandelt ScrapedGame-Objekte in Belegungsslots um.

    Diese Funktion übernimmt die gleiche Rolle wie :func:`games_to_occupancy`,
    arbeitet aber mit den einfacheren Daten, die der direkte Scraper liefert.

    Die Spieldauer wird anhand des Wettkampfnamens bestimmt (enthält er z.B.
    "A-Junioren", wird die konfigurierte Dauer für diese Mannschaftsart verwendet).
    Ist keine passende Zuordnung möglich, wird ``default_duration_minutes`` verwendet.

    Args:
        games: Liste der gescrapten Spiele.
        preparation_buffer_minutes: Puffer (Minuten) vor Anpfiff.
        default_duration_minutes: Spieldauer, wenn keine Zuordnung gefunden.
        game_durations: Zuordnung Mannschaftsart → Spieldauer in Minuten.

    Returns:
        Liste von OccupancySlot-Objekten, sortiert nach Datum und Uhrzeit.
    """
    if game_durations is None:
        game_durations = {}

    slots: list[OccupancySlot] = []

    for game in games:
        # Spiele ohne Datum oder ungültigem Zeitstempel überspringen
        try:
            kick_off = _dt.fromisoformat(game.start_date)
        except (ValueError, TypeError):
            continue

        # Spielfrei-Einträge überspringen: kein echter Spielgegner.
        # Diese Filterung erfolgt primär im Scraper; hier dient sie als
        # Absicherung gegen unvorhergesehene Datenvarianten.
        if not game.guest_team or game.guest_team.strip().lower() in {"spielfrei", "bye"}:
            continue

        # Spieldauer: Wettkampfname mit bekannten Arten abgleichen
        duration = default_duration_minutes
        comp_lower = game.competition.lower()
        for kind, dur in game_durations.items():
            if kind.lower() in comp_lower:
                duration = dur
                break

        venue = Venue(name=game.venue_name, address=game.venue_name)

        start_time = (kick_off - timedelta(minutes=preparation_buffer_minutes)).time()
        end_time = (kick_off + timedelta(minutes=duration)).time()

        slots.append(
            OccupancySlot(
                venue=venue,
                date=kick_off.date(),
                start_time=start_time,
                end_time=end_time,
                team_name=game.home_team,
                team_kind="",
                opponent=game.guest_team,
                league=game.competition,
                is_home_game=True,
            )
        )

    slots.sort(key=lambda s: (s.date, s.start_time))
    return slots
