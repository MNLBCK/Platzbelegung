# Platzbelegung

Durchsucht online Quellen (vorrangig fussball.de) nach Spielen auf einem oder mehreren bestimmten Sportplätzen und stellt die Platzbelegung übersichtlich dar.

## Architektur

Das Projekt ist in zwei klar getrennte Schichten unterteilt:

```
config.yaml               ← zentrale Konfiguration (Verein, Plätze, Saison, …)
│
├── Python-Paket (src/platzbelegung/)
│   ├── scraper.py        ← liest Daten direkt von fussball.de
│   ├── storage.py        ← speichert Snapshots als JSON mit Zeitstempel
│   ├── parser.py         ← wandelt Rohdaten in Belegungsslots um
│   ├── render_html.py    ← erzeugt offline-fähige HTML-Datei
│   ├── display.py        ← Terminal-Ausgabe (rich)
│   └── templates/
│       └── occupancy.html.j2   ← gemeinsame Jinja2-Vorlage
│
└── Web-Server (server.js / Express)
    └── liest data/latest.json  ← von Python erzeugt
        ├── GET /api/snapshot   ← vollständiger Snapshot
        ├── GET /api/games      ← Spiele gefiltert nach Sportstätte
        ├── GET /api/search     ← Sportstätten-Suche auf fussball.de
        └── GET /api/demo       ← Demo-Daten ohne Snapshot
```

**Datenfluss:**
1. `platzbelegung scrape` → scrapt fussball.de → speichert `data/latest.json` + `data/snapshots/*.json`
2. `platzbelegung html` → liest `data/latest.json` → generiert `data/latest.html`
3. Express-Server → liest `data/latest.json` → liefert dynamische Web-UI

## Voraussetzungen

- Python 3.10 oder neuer
- Node.js 18 oder neuer (nur für den Web-Server)

## Python-Installation

```bash
# Abhängigkeiten installieren (im Editable-Modus mit Dev-Extras)
pip install -e ".[dev]"
```

## Konfiguration

Alle Einstellungen werden in `config.yaml` im Repo-Root verwaltet.

### Wichtige Felder

```yaml
club:
  id: "00ES8GNAVO00000PVV0AG08LVUPGND5I"   # Vereins-ID aus fussball.de-URL
  name: "SKV Hochberg"

season: "2526"   # Saison-Code (2025/26 → "2526")

venues:           # Zu überwachende Sportstätten
  - id: "BEISPIEL_ID"
    name: "Kunstrasenplatz"

date_range:
  mode: "auto"    # oder "manual" mit start/end

scraper:
  preparation_buffer_minutes: 15   # Puffer vor Anpfiff
  game_durations:
    Herren: 90
    "A-Junioren": 70
    # …

output:
  data_dir: "data"
  html_file: "data/latest.html"
```

Die Sportstätten-ID findet sich in der fussball.de-URL:
```
https://www.fussball.de/sportstaette/-/id/<ID>
```

Alternativ kann die Web-UI verwendet werden (Suche unter `/`) oder die Suche in der API (`/api/search?q=Name`), um IDs zu ermitteln.

## Lokaler Workflow (Python-only)

```bash
# 1. Daten scrapen und Snapshot speichern
platzbelegung scrape

# 2a. Platzbelegung im Terminal anzeigen
platzbelegung show

# 2b. Statische HTML-Datei generieren (offline-fähig)
platzbelegung html
# → data/latest.html

# Eigene HTML-Ausgabedatei
platzbelegung html --output /tmp/belegung.html

# Sportstätten direkt per CLI angeben (überschreibt config.yaml)
platzbelegung scrape --venue-id ID1 ID2
```

## Web-Server (Node.js)

Der Express-Server liest `data/latest.json`, das von `platzbelegung scrape` erzeugt wurde.

```bash
npm install
npm start
# → http://localhost:3000
```

### API-Endpunkte

| Endpunkt | Beschreibung |
|---|---|
| `GET /` | Web-UI (public/index.html) |
| `GET /api/snapshot` | Vollständiger aktuellster Snapshot (JSON) |
| `GET /api/games?venueId=ID` | Spiele einer oder mehrerer Sportstätten |
| `GET /api/search?q=Name` | Sportstätten auf fussball.de suchen |
| `GET /api/demo` | Demo-Daten (kein Snapshot erforderlich) |

### Deployment

Für ein Hosting auf einem Webserver (z.B. Render, Railway, Fly.io, VPS):
1. Repo deployen
2. `npm install` ausführen
3. Sicherstellen, dass `data/latest.json` vorhanden ist (z.B. per Cronjob via Python-Scraper) oder den Scraper separat deployen
4. `npm start` (oder via PM2/systemd)

## Projektstruktur

```
Platzbelegung/
├── config.yaml                        # Zentrale Konfiguration
├── README.md
├── pyproject.toml                     # Python-Paketdefinition
├── package.json                       # Node.js-Abhängigkeiten
├── server.js                          # Express-Web-Server
├── public/                            # Statisches Frontend (Web-UI)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── src/
│   └── platzbelegung/
│       ├── __init__.py
│       ├── config.py                  # Lädt config.yaml, Legacy-Konstanten
│       ├── scraper.py                 # Direkter fussball.de HTML-Scraper
│       ├── storage.py                 # JSON-Snapshot-Verwaltung
│       ├── models.py                  # Datenmodelle (ScrapedGame, OccupancySlot, …)
│       ├── parser.py                  # Spiele → Belegungsslots
│       ├── render_html.py             # Jinja2-HTML-Generierung
│       ├── display.py                 # Terminal-Ausgabe (rich)
│       ├── main.py                    # CLI-Einstiegspunkt
│       ├── api_client.py              # Legacy: iste2 REST-API-Client
│       └── templates/
│           └── occupancy.html.j2      # Geteilte HTML-Vorlage
├── data/                              # Gitignoriert – generierte Daten
│   ├── latest.json                    # Aktuellster Snapshot
│   ├── latest.html                    # Generierte HTML-Datei
│   └── snapshots/                     # Archiv aller Snapshots
│       └── 2026-03-30T10-00-00-000000Z.json
└── tests/
    ├── test_scraper.py
    ├── test_storage.py
    ├── test_render_html.py
    ├── test_parser.py
    ├── test_display.py
    ├── test_api_client.py
    └── server.test.js
```

## Tests

```bash
# Python
pytest

# Node.js
npm test
```

## Snapshot-Format

`data/latest.json` hat folgendes Format:

```json
{
  "generated_at": "2026-03-30T10:00:00Z",
  "config": {
    "club_id": "00ES8GNAVO00000PVV0AG08LVUPGND5I",
    "club_name": "SKV Hochberg",
    "season": "2526",
    "venues": ["VENUE_ID"]
  },
  "games": [
    {
      "venueId": "VENUE_ID",
      "venueName": "Kunstrasenplatz",
      "date": "28.03.2026",
      "time": "14:00",
      "homeTeam": "SKV Hochberg – Herren",
      "guestTeam": "FC Muster",
      "competition": "Kreisliga A",
      "startDate": "2026-03-28T14:00:00",
      "scrapedAt": "2026-03-30T10:00:00Z"
    }
  ]
}
```

## Legacy-Modus (iste2 REST-API)

Das ursprüngliche Vorgehen über eine lokale [iste2/Fu-ball.de-REST-API](https://github.com/iste2/Fu-ball.de-REST-API) ist weiterhin über den `legacy`-Subcommand verfügbar:

```bash
platzbelegung legacy --club-id ID --api-url http://localhost:5000
```

## Hinweise

- Die App scrapt fussball.de; Änderungen im Layout können das Scraping beeinflussen.
- Beachte die Nutzungsbedingungen von fussball.de.
- `data/` ist gitignoriert – Snapshots werden lokal gespeichert.

