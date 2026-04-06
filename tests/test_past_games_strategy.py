from __future__ import annotations

from datetime import UTC, datetime

from platzbelegung.past_games_strategy import split_for_past_games_display


def _g(start_date: str, result: str = "") -> dict[str, str]:
    return {
        "startDate": start_date,
        "result": result,
        "homeTeam": "SKV Hochberg",
        "guestTeam": "FC Test",
    }


def test_splits_games_into_expected_sections() -> None:
    now = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    games = [
        _g("2026-04-05T13:00:00+00:00", "2:1"),  # recent result
        _g("2026-03-01T13:00:00+00:00", "1:1"),  # archive result
        _g("2026-04-06T20:00:00+00:00", ""),     # upcoming
        _g("2026-04-06T09:00:00+00:00", ""),     # likely missing result (older than 3h)
    ]

    sections = split_for_past_games_display(games, now=now)

    assert len(sections.recent_results) == 1
    assert len(sections.archive_results) == 1
    assert len(sections.upcoming_or_live) == 1
    assert len(sections.past_missing_result) == 1


def test_invalid_or_empty_start_date_falls_back_to_upcoming() -> None:
    now = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    games = [_g("", "2:1"), _g("not-a-date", "")]

    sections = split_for_past_games_display(games, now=now)

    assert sections.upcoming_or_live == games
    assert sections.recent_results == []
    assert sections.archive_results == []
    assert sections.past_missing_result == []


def test_orders_recent_results_descending() -> None:
    now = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    newer = _g("2026-04-06T10:00:00+00:00", "3:0")
    older = _g("2026-04-05T10:00:00+00:00", "1:0")

    sections = split_for_past_games_display([older, newer], now=now)

    assert sections.recent_results == [newer, older]
