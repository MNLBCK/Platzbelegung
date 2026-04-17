"""JSON-Snapshot-Verwaltung für Platzbelegung.

Speichert Scrapingergebnisse als JSON-Dateien mit Zeitstempel und stellt
Ladefunktionen bereit.  Der aktuellste Snapshot wird immer auch als
``data/latest.json`` abgelegt, damit der Web-Server ihn direkt lesen kann.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from platzbelegung.models import ScrapedGame, TrainingSession


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_snapshot(
    games: list[ScrapedGame],
    config_meta: dict,
    snapshots_dir: str = "data/snapshots",
    training_sessions: list[TrainingSession] | None = None,
) -> Path:
    """Speichert einen JSON-Snapshot mit Zeitstempel.

    Schreibt zwei Dateien:
    - ``<snapshots_dir>/<timestamp>.json`` – archivierter Snapshot
    - ``<data_dir>/latest.json``           – aktuellster Snapshot (überschrieben)

    Args:
        games: Liste der gescrapten Spiele.
        config_meta: Metadaten zur Konfiguration (wird in den Snapshot aufgenommen).
        snapshots_dir: Verzeichnis für Zeitstempel-Snapshots.
        training_sessions: Optional – Liste der gescrapten Trainingseinheiten.

    Returns:
        Pfad der neuen Snapshot-Datei.
    """
    _ensure_dir(snapshots_dir)

    now = datetime.now(timezone.utc)
    filename_ts = now.strftime("%Y-%m-%dT%H-%M-%S-%f") + "Z"  # microseconds for uniqueness

    payload = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": config_meta,
        "games": [g.to_dict() for g in games],
        "training_sessions": [t.to_dict() for t in (training_sessions or [])],
    }

    snap_path = Path(snapshots_dir) / f"{filename_ts}.json"
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Aktuellsten Snapshot in data_dir/latest.json ablegen
    data_dir = Path(snapshots_dir).parent
    _ensure_dir(data_dir)
    latest_path = data_dir / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return snap_path


def load_latest_snapshot(data_dir: str = "data") -> dict | None:
    """Lädt den zuletzt gespeicherten Snapshot.

    Returns:
        Snapshot-Dict oder ``None``, wenn kein Snapshot vorhanden ist.
    """
    latest_path = Path(data_dir) / "latest.json"
    if not latest_path.exists():
        return None
    with open(latest_path, encoding="utf-8") as f:
        return json.load(f)


def load_snapshot(path: str | Path) -> dict:
    """Lädt einen bestimmten Snapshot aus einer Datei."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_snapshots(snapshots_dir: str = "data/snapshots") -> list[Path]:
    """Gibt alle vorhandenen Snapshot-Dateien aufsteigend sortiert zurück."""
    d = Path(snapshots_dir)
    if not d.exists():
        return []
    return sorted(d.glob("*.json"))


def games_from_snapshot(snapshot: dict) -> list[ScrapedGame]:
    """Extrahiert ScrapedGame-Objekte aus einem geladenen Snapshot-Dict."""
    scraped_at = snapshot.get("generated_at", "")
    return [
        ScrapedGame.from_dict(g, scraped_at)
        for g in snapshot.get("games", [])
    ]


def training_sessions_from_snapshot(snapshot: dict) -> list[TrainingSession]:
    """Extrahiert TrainingSession-Objekte aus einem geladenen Snapshot-Dict."""
    scraped_at = snapshot.get("generated_at", "")
    return [
        TrainingSession.from_dict(t, scraped_at)
        for t in snapshot.get("training_sessions", [])
    ]

