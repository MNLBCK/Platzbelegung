"""Prototypische Strategie zur Anzeige vergangener Spiele.

Dieses Modul kapselt eine kleine, testbare Logik für die UI-Strategie:
- Spiele werden nach Zeitbezug und Ergebnis in sinnvolle Bereiche aufgeteilt.
- Vergangene Spiele mit Ergebnis werden priorisiert hervorgehoben.
- Vergangene Spiele ohne Ergebnis werden separat markiert (Datenqualität).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class PastGamesSections:
    """Aufbereitete Sektionen für eine Platzbelegungsansicht."""

    recent_results: list[dict[str, Any]]
    upcoming_or_live: list[dict[str, Any]]
    past_missing_result: list[dict[str, Any]]
    archive_results: list[dict[str, Any]]


def _parse_start_date(raw: str) -> datetime | None:
    if not raw:
        return None
    value = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _has_result(game: dict[str, Any]) -> bool:
    result = str(game.get("result", "")).strip()
    return bool(result and result != "-:-")


def split_for_past_games_display(
    games: list[dict[str, Any]],
    *,
    now: datetime,
    recent_window_days: int = 14,
    started_grace_hours: int = 3,
) -> PastGamesSections:
    """Teilt Spiele in UI-Sektionen für Vergangenheit/Gegenwart/Zukunft auf.

    Args:
        games: Rohspiele aus API/Frontend.
        now: Referenzzeitpunkt (UTC).
        recent_window_days: Fenster für "letzte Ergebnisse".
        started_grace_hours: Ab wann ein gestartetes Spiel ohne Ergebnis als
            "Ergebnis fehlt" behandelt wird.
    """

    now_utc = now.astimezone(UTC)
    recent_cutoff = now_utc - timedelta(days=recent_window_days)
    missing_cutoff = now_utc - timedelta(hours=started_grace_hours)

    recent_results: list[dict[str, Any]] = []
    upcoming_or_live: list[dict[str, Any]] = []
    past_missing_result: list[dict[str, Any]] = []
    archive_results: list[dict[str, Any]] = []

    for game in games:
        start = _parse_start_date(str(game.get("startDate", "")))
        if start is None:
            # Konservativ in Zukunft/Live belassen, damit nichts verloren geht.
            upcoming_or_live.append(game)
            continue

        has_result = _has_result(game)
        if has_result:
            if start >= recent_cutoff:
                recent_results.append(game)
            else:
                archive_results.append(game)
            continue

        if start <= missing_cutoff:
            past_missing_result.append(game)
        else:
            upcoming_or_live.append(game)

    recent_results.sort(key=lambda g: str(g.get("startDate", "")), reverse=True)
    archive_results.sort(key=lambda g: str(g.get("startDate", "")), reverse=True)
    upcoming_or_live.sort(key=lambda g: str(g.get("startDate", "")))
    past_missing_result.sort(key=lambda g: str(g.get("startDate", "")), reverse=True)

    return PastGamesSections(
        recent_results=recent_results,
        upcoming_or_live=upcoming_or_live,
        past_missing_result=past_missing_result,
        archive_results=archive_results,
    )
