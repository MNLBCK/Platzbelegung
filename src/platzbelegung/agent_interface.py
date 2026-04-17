"""Agentische Schnittstelle für Trainingsquellen-Anfragen.

Minimal-CLI zum Einreichen, Reviewen und Genehmigen/Verwerfen von "Anfragen"
für Trainingszeitenquellen. Designed für internen Gebrauch (MSZ). Es erfolgt
keine automatische Veröffentlichung von Webseiten-Anfragen — Genehmigung ist
ein manueller Schritt (`approve`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from getpass import getuser
from typing import Any

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DATA_DIR = os.path.join(ROOT, "data")
REQUESTS_DIR = os.path.join(DATA_DIR, "requests")
PENDING_DIR = os.path.join(REQUESTS_DIR, "pending")
PROCESSED_DIR = os.path.join(REQUESTS_DIR, "processed")
TRAINING_SOURCES = os.path.join(DATA_DIR, "training_sources.json")


def ensure_dirs() -> None:
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    if not os.path.exists(TRAINING_SOURCES):
        with open(TRAINING_SOURCES, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def submit(args: argparse.Namespace) -> int:
    ensure_dirs()
    body = {}
    if args.json:
        try:
            body = json.loads(args.json)
        except json.JSONDecodeError as e:
            print("Ungültiges JSON:", e)
            return 2
    else:
        # collect fields
        body = {
            "source_url": args.source_url,
            "text": args.text,
            "club_name": args.club_name,
            "team": args.team,
            "submitter": args.submitter or getuser(),
            "note": args.note,
        }

    meta = {
        "id": f"req-{timestamp()}",
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "submitter": body.get("submitter", getuser()),
        "body": body,
    }

    filename = f"{meta['id']}.json"
    path = os.path.join(PENDING_DIR, filename)
    write_json(path, meta)
    print("Gespeichert:", path)
    return 0


def list_pending(args: argparse.Namespace) -> int:
    ensure_dirs()
    files = sorted(os.listdir(PENDING_DIR))
    for f in files:
        print(f)
    return 0


def _find_url_in_text(text: str) -> str | None:
    m = re.search(r"https?://[\w\-\./?&=%#]+", text)
    return m.group(0) if m else None


def review_request(payload: dict) -> dict:
    """Einfache Heuristik-Review: liefert eine Empfehlung, keine automatische Freigabe."""
    body = payload.get("body", {}) if isinstance(payload, dict) else {}
    text = (body.get("text") or "")
    source = body.get("source_url") or _find_url_in_text(text) or ""

    decision = "need_manual_review"
    note = ""
    suggested = {"source_url": source}

    if source:
        # einfache Heuristiken
        if re.search(r"train|training|zeiten|trainingsplan", source + text, re.IGNORECASE):
            decision = "suggest_accept"
            note = "Quelle enthält Trainings-bezogene Begriffe (heuristisch)."
        else:
            decision = "need_manual_review"
            note = "Keine klaren Trainingsbegriffe gefunden; manuelle Prüfung empfohlen."

    # Team extractions from path or anchor-like text
    team = body.get("team") or ""
    if not team and source:
        # last path segment
        try:
            seg = source.rstrip("/").split("/")[-1]
            seg = seg.replace("-", " ").replace("%C3%9F", "ss")
            if seg and len(seg) < 40:
                team = seg
        except Exception:
            team = ""

    suggested["team"] = team

    return {"decision": decision, "note": note, "suggested": suggested}


def review(args: argparse.Namespace) -> int:
    ensure_dirs()
    path = os.path.join(PENDING_DIR, args.request_file)
    if not os.path.exists(path):
        print("Anfrage nicht gefunden:", path)
        return 2
    payload = read_json(path)
    result = review_request(payload)
    payload.setdefault("reviews", []).append({
        "reviewed_at": datetime.utcnow().isoformat() + "Z",
        "reviewer": args.reviewer or getuser(),
        "result": result,
    })
    write_json(path, payload)
    print("Review gespeichert in:", path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def approve(args: argparse.Namespace) -> int:
    ensure_dirs()
    path = os.path.join(PENDING_DIR, args.request_file)
    if not os.path.exists(path):
        print("Anfrage nicht gefunden:", path)
        return 2

    # safety: require explicit confirmation unless --yes
    if not args.yes:
        ans = input("Genehmigen und zur training_sources.json hinzufügen? (yes/no): ")
        if ans.strip().lower() != "yes":
            print("Abgebrochen")
            return 1

    payload = read_json(path)
    body = payload.get("body", {})
    source = body.get("source_url") or _find_url_in_text(body.get("text", "") or "")
    entry = {
        "club_name": body.get("club_name") or payload.get("submitter") or "",
        "team": body.get("team") or "",
        "source_url": source or "",
        "added_at": datetime.utcnow().isoformat() + "Z",
        "added_by": args.approver or getuser(),
    }

    # append to training_sources.json
    sources = []
    try:
        sources = read_json(TRAINING_SOURCES)
    except Exception:
        sources = []
    sources.append(entry)
    write_json(TRAINING_SOURCES, sources)

    # move pending -> processed
    dest = os.path.join(PROCESSED_DIR, os.path.basename(path))
    shutil.move(path, dest)
    print("Anfrage genehmigt und hinzugefügt:", dest)
    return 0


def reject(args: argparse.Namespace) -> int:
    ensure_dirs()
    path = os.path.join(PENDING_DIR, args.request_file)
    if not os.path.exists(path):
        print("Anfrage nicht gefunden:", path)
        return 2
    payload = read_json(path)
    payload.setdefault("reviews", []).append({
        "reviewed_at": datetime.utcnow().isoformat() + "Z",
        "reviewer": args.reviewer or getuser(),
        "result": {"decision": "rejected", "note": args.reason or "Keine Angabe"},
    })
    dest = os.path.join(PROCESSED_DIR, os.path.basename(path))
    write_json(dest, payload)
    os.remove(path)
    print("Anfrage verworfen:", dest)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="platzbelegung-agent")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("submit")
    s.add_argument("--json", help="Komplettes Anfrage-JSON")
    s.add_argument("--source-url")
    s.add_argument("--text")
    s.add_argument("--club-name")
    s.add_argument("--team")
    s.add_argument("--submitter")
    s.add_argument("--note")
    s.set_defaults(func=submit)

    lp = sub.add_parser("list-pending")
    lp.set_defaults(func=list_pending)

    r = sub.add_parser("review")
    r.add_argument("request_file", help="Dateiname in data/requests/pending/")
    r.add_argument("--reviewer")
    r.set_defaults(func=review)

    a = sub.add_parser("approve")
    a.add_argument("request_file", help="Dateiname in data/requests/pending/")
    a.add_argument("--approver")
    a.add_argument("--yes", action="store_true")
    a.set_defaults(func=approve)

    rej = sub.add_parser("reject")
    rej.add_argument("request_file", help="Dateiname in data/requests/pending/")
    rej.add_argument("--reviewer")
    rej.add_argument("--reason")
    rej.set_defaults(func=reject)

    args = p.parse_args(argv)
    if not hasattr(args, "func"):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
