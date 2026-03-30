"""Tests für storage.py (JSON-Snapshot-Verwaltung)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from platzbelegung.models import ScrapedGame
from platzbelegung.storage import (
    games_from_snapshot,
    list_snapshots,
    load_latest_snapshot,
    load_snapshot,
    save_snapshot,
)


def _make_games() -> list[ScrapedGame]:
    return [
        ScrapedGame(
            venue_id="V1",
            venue_name="Platz 1",
            date="01.04.2026",
            time="15:00",
            home_team="SKV Hochberg",
            guest_team="FC Muster",
            competition="Kreisliga A",
            start_date="2026-04-01T15:00:00",
            scraped_at="2026-03-30T10:00:00Z",
        ),
        ScrapedGame(
            venue_id="V2",
            venue_name="Platz 2",
            date="05.04.2026",
            time="11:00",
            home_team="SKV Hochberg II",
            guest_team="SV Test",
            competition="Kreisliga B",
            start_date="2026-04-05T11:00:00",
            scraped_at="2026-03-30T10:00:00Z",
        ),
    ]


class TestSaveSnapshot:
    def test_creates_snapshot_file(self, tmp_path):
        games = _make_games()
        snap_path = save_snapshot(
            games,
            config_meta={"club_id": "TEST"},
            snapshots_dir=str(tmp_path / "snapshots"),
        )
        assert snap_path.exists()

    def test_snapshot_contains_games(self, tmp_path):
        games = _make_games()
        snap_path = save_snapshot(
            games,
            config_meta={"club_id": "TEST"},
            snapshots_dir=str(tmp_path / "snapshots"),
        )
        with open(snap_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["games"]) == 2
        assert data["games"][0]["venueId"] == "V1"

    def test_creates_latest_json(self, tmp_path):
        games = _make_games()
        snapshots_dir = tmp_path / "snapshots"
        save_snapshot(
            games,
            config_meta={},
            snapshots_dir=str(snapshots_dir),
        )
        latest = tmp_path / "latest.json"
        assert latest.exists()

    def test_config_meta_is_stored(self, tmp_path):
        meta = {"club_id": "CLUB001", "season": "2526"}
        snap_path = save_snapshot(
            _make_games(),
            config_meta=meta,
            snapshots_dir=str(tmp_path / "snapshots"),
        )
        with open(snap_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["config"]["club_id"] == "CLUB001"

    def test_generated_at_is_present(self, tmp_path):
        snap_path = save_snapshot(
            _make_games(),
            config_meta={},
            snapshots_dir=str(tmp_path / "snapshots"),
        )
        with open(snap_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "generated_at" in data
        assert "T" in data["generated_at"]


class TestLoadLatestSnapshot:
    def test_returns_none_when_missing(self, tmp_path):
        result = load_latest_snapshot(str(tmp_path))
        assert result is None

    def test_returns_snapshot_after_save(self, tmp_path):
        save_snapshot(
            _make_games(),
            config_meta={"club_id": "X"},
            snapshots_dir=str(tmp_path / "snapshots"),
        )
        snapshot = load_latest_snapshot(str(tmp_path))
        assert snapshot is not None
        assert len(snapshot["games"]) == 2


class TestListSnapshots:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        assert list_snapshots(str(tmp_path)) == []

    def test_returns_snapshot_paths(self, tmp_path):
        snap_dir = str(tmp_path / "snapshots")
        save_snapshot(_make_games(), config_meta={}, snapshots_dir=snap_dir)
        snaps = list_snapshots(snap_dir)
        assert len(snaps) == 1
        assert snaps[0].suffix == ".json"

    def test_multiple_snapshots_sorted(self, tmp_path):
        snap_dir = str(tmp_path / "snapshots")
        save_snapshot(_make_games(), config_meta={}, snapshots_dir=snap_dir)
        save_snapshot(_make_games(), config_meta={}, snapshots_dir=snap_dir)
        snaps = list_snapshots(snap_dir)
        assert len(snaps) == 2
        assert snaps[0] <= snaps[1]


class TestGamesFromSnapshot:
    def test_extracts_scraped_games(self, tmp_path):
        snap_path = save_snapshot(
            _make_games(),
            config_meta={},
            snapshots_dir=str(tmp_path / "snapshots"),
        )
        snapshot = load_snapshot(snap_path)
        games = games_from_snapshot(snapshot)
        assert len(games) == 2
        assert isinstance(games[0], ScrapedGame)
        assert games[0].venue_id == "V1"

    def test_empty_snapshot_returns_empty_list(self):
        games = games_from_snapshot({"games": []})
        assert games == []
