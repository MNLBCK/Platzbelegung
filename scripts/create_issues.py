#!/usr/bin/env python3
"""
Create 12 project-improvement issues in MNLBCK/Platzbelegung via the GitHub REST API.

Usage:
    GITHUB_TOKEN=<your_token> python scripts/create_issues.py

Environment variables:
    GITHUB_TOKEN or GH_TOKEN  – Personal access token with repo scope
    GITHUB_REPO               – Optional override, defaults to MNLBCK/Platzbelegung
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ.get("GITHUB_REPO", "MNLBCK/Platzbelegung")
API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"

ISSUES = [
    {
        "title": "Vereinheitlichung der Parsing-Logik in Python und PHP",
        "labels": ["refactor", "enhancement"],
        "body": """\
Aktuell wird Matchplan-/Spiel-Parsing sowohl in `src/platzbelegung/scraper.py` als auch in `backend.php` umgesetzt. Das erhöht Wartungsaufwand und Fehleranfälligkeit bei Änderungen an fussball.de.

## Ziel

* Eine einzige Source of Truth für Parsing und Normalisierung definieren
* PHP-Backend auf Snapshot-Auslieferung bzw. schlanke API-Logik reduzieren
* Doppelte Datums-, Venue- und Matchplan-Parser entfernen

## Akzeptanzkriterien

* Parsing fachlicher Spieldaten liegt nur noch in einer Schicht
* Keine doppelte HTML-Parsing-Logik mehr in Python und PHP
* Bestehende Tests laufen weiter oder werden angepasst
* Dokumentation im README aktualisiert

## Betroffene Dateien

* `src/platzbelegung/scraper.py`
* `backend.php`
""",
    },
    {
        "title": "Konfigurationszugriff ohne Python-Shell-Aufrufe aus PHP umbauen",
        "labels": ["refactor", "enhancement"],
        "body": """\
`backend.php` liest und schreibt `config.yaml` aktuell über `python3 -c ...`-Aufrufe. Das koppelt das Web-Backend unnötig an Python und PyYAML.

## Ziel

* Konfigurationszugriff vereinfachen und robuster machen
* Shell-Aufrufe aus PHP für Config-Lesen/Schreiben entfernen
* Gemeinsamen Konfigurationsvertrag definieren, z. B. JSON für Web-seitige Schreibzugriffe

## Akzeptanzkriterien

* Kein `shell_exec`/`exec` mehr für Config-Handling in PHP
* Fehlerfälle sauber behandelt
* Deployment ohne implizite Python-Abhängigkeit für reine Web-Nutzung möglich
* README aktualisiert

## Betroffene Dateien

* `backend.php`
* `src/platzbelegung/config.py`
* `README.md`
""",
    },
    {
        "title": "Hardening der PHP-API für Suche, Admin-Endpunkte und Config-Änderungen",
        "labels": ["security", "enhancement"],
        "body": """\
Mehrere Endpunkte ziehen externe Inhalte, speichern Konfiguration oder schützen Admin-Daten nur per Passwort im Query-String. Das sollte robuster und sicherer werden.

## Ziel

* Query-String-Passwort für Admin-Endpunkt ablösen oder absichern
* Logging/Audit für Schreibzugriffe ergänzen
* Rate Limiting bzw. Schutz vor Missbrauch für Such-/Matchplan-Endpunkte vorbereiten
* Fehlerbilder intern besser unterscheidbar machen

## Akzeptanzkriterien

* Admin-Zugriff nicht mehr ausschließlich über Passwort im Query-String
* Schreibzugriffe auf `/api/config/*` nachvollziehbar protokolliert
* Externe Requests haben saubere Fehlerbehandlung
* Technische Fehler werden intern differenziert geloggt

## Betroffene Dateien

* `backend.php`
""",
    },
    {
        "title": "Versioniertes Snapshot-Schema für `latest.json` einführen",
        "labels": ["enhancement", "refactor"],
        "body": """\
`data/latest.json` ist das zentrale Austauschformat zwischen Scraper, HTML-Generator und Web-UI. Aktuell fehlt ein explizit versioniertes Schema.

## Ziel

* `schemaVersion` im Snapshot ergänzen
* Datenvertrag für `games`, Meta-Felder und optionale Felder dokumentieren
* Vorbereitung für zukünftige Erweiterungen wie Logos, Resultate, zusätzliche Venue-Metadaten

## Akzeptanzkriterien

* Snapshot enthält Schema-Version
* Konsumenten prüfen oder tolerieren die Version
* README dokumentiert Format und Migrationsstrategie
* Abwärtskompatibilität bewusst geregelt

## Betroffene Dateien

* `README.md`
* `storage.py`
* `backend.php`
* Frontend-Konsumenten von Snapshot-Daten
""",
    },
    {
        "title": "Einheitliches Datums- und Zeitzonenmodell im gesamten Projekt",
        "labels": ["enhancement", "refactor"],
        "body": """\
Es gibt aktuell gemischte Formate mit lokalen Datumswerten, ISO-Strings und teils UTC-Timestamps. Das ist funktional, aber inkonsistent.

## Ziel

* Einheitliches internes Zeitformat definieren
* ISO-8601 mit klarer Zeitzonenstrategie verwenden
* UI-Formatierung strikt von Speicher-/Transportformat trennen

## Akzeptanzkriterien

* `startDate`/`generated_at`/`scraped_at` sind konsistent dokumentiert
* Python und PHP erzeugen kompatible Zeitwerte
* Sortierung und Anzeige bleiben korrekt
* Tests decken Randfälle ab

## Betroffene Dateien

* `src/platzbelegung/scraper.py`
* `src/platzbelegung/parser.py`
* `backend.php`
""",
    },
    {
        "title": "`public/app.js` modularisieren und Verantwortlichkeiten trennen",
        "labels": ["refactor", "enhancement"],
        "body": """\
`public/app.js` bündelt State, Storage, API-Zugriffe, Kalender-Rendering, Clubsuche, SG-Erkennung und Modal-UI in einer großen Datei. Das erschwert Wartung und Testing.

## Ziel

* Datei in sinnvolle Module aufteilen
* Verantwortlichkeiten trennen, z. B. `state`, `api`, `calendar`, `clubs`, `venues`, `ui`
* Grundlage für bessere Tests und kleinere Änderungen schaffen

## Akzeptanzkriterien

* `app.js` ist deutlich kleiner oder nur noch Einstiegspunkt
* Kein Verlust bestehender Funktionen
* Initialisierung und State-Fluss sind nachvollziehbarer
* Browser-kompatibler Build-freier Ansatz oder bewusstes Build-Setup dokumentiert

## Betroffene Dateien

* `public/app.js`
""",
    },
    {
        "title": "Clientseitige Persistenz konsolidieren",
        "labels": ["refactor", "enhancement"],
        "body": """\
Der Frontend-State wird aktuell gemischt in Cookies und `sessionStorage` gehalten. Das sollte sauberer getrennt werden.

## Ziel

* Persistenzkonzept definieren
* UI-Präferenzen und Session-Daten klar trennen
* Cookies nur verwenden, wenn sie serverseitig wirklich nötig sind

## Akzeptanzkriterien

* Dokumentiertes Persistenzmodell
* Weniger Cookie-Abhängigkeit
* Bestehende Features wie letzte Vereine, Venue-Filter und View-State bleiben erhalten
* Migration bestehender gespeicherter Werte bedacht

## Betroffene Dateien

* `public/app.js`
""",
    },
    {
        "title": "Testabdeckung nach PHP-Migration für API und Frontend ausbauen",
        "labels": ["testing", "enhancement"],
        "body": """\
Python-Tests sind vorhanden, aber für das PHP-Backend und das Frontend fehlt weitgehend automatisierte Absicherung.

## Ziel

* Kritische API-Endpunkte testen
* Zentrale Frontend-Logik testbar machen
* Regressionsschutz für Venue-Filter, SG-Erkennung, Deduplizierung und Kalenderansichten erhöhen

## Akzeptanzkriterien

* Automatisierte Tests für zentrale API-Endpunkte vorhanden
* Mindestens Kernlogik im Frontend testbar
* `npm test` ist nicht mehr nur ein Placeholder
* Teststrategie im README oder CONTRIBUTING beschrieben

## Betroffene Dateien

* `package.json`
* `backend.php`
* `public/app.js`
* `tests/`
""",
    },
    {
        "title": "CI-Pipeline für Tests, Linting und Konsistenzprüfungen ergänzen",
        "labels": ["ci", "enhancement"],
        "body": """\
Das Repo kombiniert Python, PHP und statisches Frontend. Eine kleine CI würde Fehler früh sichtbar machen.

## Ziel

* Automatische Testausführung bei PRs
* Syntax-/Lint-Checks für Python und PHP
* Optionale Konsistenzchecks für Versionsnummern und Doku

## Akzeptanzkriterien

* CI läuft bei Push/PR
* Python-Tests werden ausgeführt
* PHP-Syntax wird geprüft
* Fehlerhafte Änderungen blockieren frühzeitig

## Betroffene Dateien

* GitHub Actions Workflow
* `pyproject.toml`
* `package.json`
""",
    },
    {
        "title": "Spieldauer-Regeln robuster und expliziter modellieren",
        "labels": ["enhancement", "refactor"],
        "body": """\
Die Belegungsdauer wird aktuell per Text-Matching auf `competition` ermittelt. Das ist pragmatisch, aber fragil.

## Ziel

* Regelwerk für Spieldauern expliziter machen
* Konfigurierbare Prioritäten und Overrides ermöglichen
* Weniger Abhängigkeit von freien Texten in Wettbewerbsnamen

## Akzeptanzkriterien

* Dauerlogik ist nachvollziehbar und testbar
* Konfiguration für Sonderfälle möglich
* Parser bleibt kompatibel mit bestehenden Daten
* Randfälle sind durch Tests abgedeckt

## Betroffene Dateien

* `src/platzbelegung/parser.py`
* `src/platzbelegung/config.py`
""",
    },
    {
        "title": "Strukturierte Fehlerbehandlung und Logging für Scraper und Backend",
        "labels": ["enhancement", "logging"],
        "body": """\
Mehrere Fehlerpfade geben nur generische Meldungen zurück. Für Betrieb, Diagnose und Wartung wären strukturiertere Fehler hilfreich.

## Ziel

* Interne Fehlercodes oder Kategorien definieren
* Upstream-/Netzwerk-/Parsingfehler klar unterscheiden
* Nutzerfreundliche Meldungen von internem Logging trennen

## Akzeptanzkriterien

* Logging enthält mehr Kontext
* HTTP-Fehlerpfade sind konsistent
* Nutzer bekommen verständliche Meldungen
* Entwickler können Ursachen leichter nachvollziehen

## Betroffene Dateien

* `src/platzbelegung/scraper.py`
* `backend.php`
""",
    },
    {
        "title": "Lizenz- und Versionsangaben im Repo vereinheitlichen",
        "labels": ["maintenance", "enhancement"],
        "body": """\
Aktuell ist im Python-Paket MIT hinterlegt, in `package.json` jedoch ISC. Außerdem wird Version an mehreren Stellen geführt.

## Ziel

* Einheitliche Lizenzangabe im gesamten Repo
* Klare Single Source of Truth für Versionen
* Release-Metadaten konsistent ableiten

## Akzeptanzkriterien

* Keine widersprüchlichen Lizenzangaben mehr
* Versionsquelle ist dokumentiert
* Build-/Release-Meta folgt konsistent daraus

## Betroffene Dateien

* `pyproject.toml`
* `package.json`
* `backend.php` / `VERSION` / `BUILD_META.json`
""",
    },
]


def require_github_token() -> str:
    """Read and return the GitHub token from the environment, exiting if absent."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print(
            "ERROR: Set GITHUB_TOKEN or GH_TOKEN to a personal access token with repo scope.",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def github_request(method: str, path: str, token: str, data: dict | None = None) -> dict:
    """Send a GitHub REST API request and return the parsed JSON response.

    Args:
        method: HTTP method (GET, POST, …).
        path:   API path starting with '/', e.g. '/repos/owner/repo/issues'.
        token:  GitHub personal access token.
        data:   Optional request body, serialised to JSON.

    Returns:
        Parsed JSON response as a dict (or list cast to dict by caller).

    Raises:
        urllib.error.HTTPError: On any non-2xx response.
    """
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "platzbelegung-issue-creator/1.0",
    }
    body = json.dumps(data).encode() if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        print(f"HTTP {exc.code} for {method} {url}: {error_body}", file=sys.stderr)
        raise


def list_existing_issues(token: str) -> set[str]:
    """Return the set of open issue titles already present in the repo."""
    titles: set[str] = set()
    page = 1
    while True:
        items = github_request(
            "GET",
            f"/repos/{REPO}/issues?state=open&per_page=100&page={page}",
            token,
        )
        if not items:
            break
        for item in items:
            if "pull_request" not in item:
                titles.add(item["title"])
        if len(items) < 100:
            break
        page += 1
    return titles


def ensure_label(label: str, token: str) -> None:
    """Create the label if it doesn't exist yet (best-effort)."""
    defaults = {
        "enhancement": ("a2eeef", "New feature or request"),
        "refactor": ("e4e669", "Code restructuring without behaviour change"),
        "security": ("d93f0b", "Security-related change"),
        "ci": ("0075ca", "Continuous integration"),
        "testing": ("0e8a16", "Test coverage"),
        "logging": ("bfd4f2", "Logging and diagnostics"),
        "maintenance": ("e4e669", "Chores and housekeeping"),
    }
    try:
        github_request("GET", f"/repos/{REPO}/labels/{urllib.parse.quote(label)}", token)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        color, description = defaults.get(label, ("cccccc", label))
        try:
            github_request(
                "POST",
                f"/repos/{REPO}/labels",
                token,
                {"name": label, "color": color, "description": description},
            )
            print(f"  [label created] {label}")
        except urllib.error.HTTPError as create_exc:
            print(
                f"  [label skipped] {label} (HTTP {create_exc.code} – could not create)",
            )


def main() -> None:
    token = require_github_token()
    print(f"Repository : {REPO}")
    print(f"Issues     : {len(ISSUES)}")
    print()

    print("Fetching existing issues …")
    existing = list_existing_issues(token)
    print(f"Found {len(existing)} open issue(s) already.\n")

    created = 0
    skipped = 0
    failed = 0

    for i, issue in enumerate(ISSUES, start=1):
        title = issue["title"]
        if title in existing:
            print(f"[{i:02d}] SKIPPED  – already exists: {title}")
            skipped += 1
            continue

        for label in issue.get("labels", []):
            ensure_label(label, token)

        try:
            result = github_request(
                "POST",
                f"/repos/{REPO}/issues",
                token,
                {
                    "title": title,
                    "body": issue["body"],
                    "labels": issue.get("labels", []),
                },
            )
            print(f"[{i:02d}] CREATED  #{result['number']} – {title}")
            created += 1
        except urllib.error.HTTPError:
            print(f"[{i:02d}] FAILED   – {title}", file=sys.stderr)
            failed += 1

    print()
    print(f"Done. Created: {created}  Skipped: {skipped}  Failed: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
