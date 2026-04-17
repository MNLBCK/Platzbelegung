# Platzbelegung

Durchsucht online Quellen (vorrangig fussball.de) nach Spielen auf einem oder mehreren bestimmten Sportplätzen und stellt die Platzbelegung übersichtlich dar.

## Datenquellen

Die Anwendung nutzt primär die **club matchplan API** (`ajax.club.matchplan`) von fussball.de, da diese stabiler und strukturierter ist als das HTML-Parsing von Sportstätten-Seiten.

### Warum nicht mehr Sportstätten-Seiten?

Die direkten Sportstätten-URLs (`https://www.fussball.de/sportstaette/-/id/...`) zeigen nicht mehr zuverlässig alle Spiele an. Die HTML-Struktur ändert sich häufig und ist nicht für maschinelles Auslesen gedacht. Daher ist dieser Ansatz als **deprecated** markiert.

### Club-first Architektur

Der empfohlene Workflow ist:
1. **Club Matchplan scrapen** → alle Spiele des Vereins über `ajax.club.matchplan`
2. **Nach Sportstätten filtern** → nur Spiele auf den konfigurierten Plätzen anzeigen

Dies ist robuster und einfacher zu warten, da die API-Struktur stabiler ist als HTML-Parsing.

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
└── Web-Server (PHP)
    └── liest data/latest.json  ← von Python erzeugt
        ├── GET /api/snapshot   ← vollständiger Snapshot
        ├── GET /api/games      ← Spiele gefiltert nach Sportstätte
        ├── GET /api/search     ← Sportstätten-Suche auf fussball.de
        └── GET /api/demo       ← Demo-Daten ohne Snapshot
```

**Datenfluss:**
1. `platzbelegung scrape` → scrapt club matchplan (ajax.club.matchplan) → filtert nach Sportstätten → speichert `data/latest.json` + `data/snapshots/*.json`
2. `platzbelegung html` → liest `data/latest.json` → generiert `data/latest.html`
3. PHP-Server → liest `data/latest.json` → liefert dynamische Web-UI

**Scraping-Strategie:**
- **Primär:** Club matchplan API (`scraper.scrape_club_matchplan()`) – stabil, strukturiert

## Voraussetzungen

- Python 3.10 oder neuer
- PHP 8.1 oder neuer (nur für den Web-Server)

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
#    Verwendet primär club matchplan API, filtert nach konfigurierten Sportstätten
platzbelegung scrape

# 2a. Platzbelegung im Terminal anzeigen
platzbelegung show

# 2b. Statische HTML-Datei generieren (offline-fähig)
platzbelegung html
# → data/latest.html

# Eigene HTML-Ausgabedatei
platzbelegung html --output /tmp/belegung.html
```

## Web-Server (PHP)

Der PHP-Server liest `data/latest.json`, das von `platzbelegung scrape` erzeugt wurde.

```bash
php -S 0.0.0.0:3210 backend.php
# → http://localhost:3210
```

### API-Endpunkte

| Endpunkt | Beschreibung |
|---|---|
| `GET /` | Web-UI (public/index.html) |
| `GET /api/snapshot` | Vollständiger aktuellster Snapshot (JSON) |
| `GET /api/games?venueId=ID` | Spiele einer oder mehrerer Sportstätten |
| `GET /api/search?q=Name` | Sportstätten auf fussball.de suchen |
| `GET /api/admin/club-parse-stats?password=...` | Anonyme Nutzungsstatistik pro Verein (sortiert nach Parse-Anzahl) |
| `GET /api/demo` | Demo-Daten (kein Snapshot erforderlich) |

Für die Statistik muss serverseitig ein Passwort gesetzt sein (nicht im Git):

- entweder über Umgebungsvariable `PLATZBELEGUNG_STATS_PASSWORD`
- oder über eine lokale Datei `.stats_password` im Repo-Root (eine Zeile mit dem Passwort)

### Deployment

#### Variante A: eigener Server / VPS

Für ein Hosting auf einem Webserver (z.B. VPS, Render, Railway, Fly.io):
1. Repo deployen
2. Sicherstellen, dass `data/latest.json` vorhanden ist (z.B. per Cronjob via Python-Scraper) oder den Scraper separat deployen
3. `php -S 0.0.0.0:3210 backend.php` starten (oder äquivalent via Prozessmanager)

#### Variante B: Shared Hosting / Webspace mit FTP-Upload

Für klassisches Webhosting ohne dauerhaft laufende Python- oder Node-Prozesse kann die Anwendung ebenfalls betrieben werden. Der typische Ablauf ist:

1. **Projekt lokal vorbereiten**
   - Python-Abhängigkeiten lokal installieren
   - `config.yaml` mit Vereins-ID, Saison und Sportstätten pflegen
   - Snapshot lokal erzeugen:

   ```bash
   platzbelegung scrape
   ```

   Dadurch entsteht insbesondere `data/latest.json`.

2. **Dateien auf den Server hochladen**
   - per **FTP/SFTP** in das Zielverzeichnis der Domain oder Subdomain hochladen, z.B. `platzbelegung.sghochx.de`
   - mindestens diese Dateien/Ordner werden benötigt:
     - `backend.php`
     - `public/`
     - `data/latest.json`
     - optional `data/latest.html`
     - `config.yaml` (nur nötig, wenn die Web-UI Konfigurationen lesen/ändern soll)

3. **Document Root auf `public/` zeigen lassen**
   - idealerweise zeigt die Domain/Subdomain direkt auf den Ordner `public/`
   - falls der Hoster keinen separaten Document Root pro Subdomain erlaubt, müssen `public/index.html`, `public/app.js` und `public/style.css` im Webroot liegen und Requests an `backend.php` weitergeleitet werden

4. **PHP aktivieren**
   - erforderlich ist PHP **8.1 oder neuer**
   - `backend.php` muss im Zielsystem ausgeführt werden können

5. **Snapshot regelmäßig aktualisieren**
   - auf einfachem Shared Hosting läuft der Python-Scraper oft **nicht dauerhaft direkt auf dem Server**
   - daher gibt es zwei praxistaugliche Wege:
     - **lokal oder auf einem anderen Host scrapen** und anschließend `data/latest.json` per FTP/SFTP hochladen
     - falls beim Hoster Python + Cronjobs verfügbar sind, den Scraper direkt dort per Cron ausführen

#### Beispiel: lokale Aktualisierung + FTP-Upload

Ein typischer manueller Release-/Update-Ablauf sieht so aus:

```bash
# lokal neue Daten holen
platzbelegung scrape

# danach die erzeugte Datei hochladen
# hochzuladen ist mindestens: data/latest.json
```

Wenn der Hoster kein SSH anbietet, genügt bereits ein FTP-Client wie FileZilla, Cyberduck oder das Deployment-Tool des Providers.

#### Release per Skript

Für versionierte Releases gibt es zusätzlich ein Release-Skript. Es synchronisiert die relevanten Versionsdateien, erstellt Commit + Tag, pusht beides und legt anschließend ein GitHub Release mit automatisch generierten Notes an.

```bash
bash scripts/release.sh v0.1.71
```

Das Skript aktualisiert dabei:

- `VERSION`
- `pyproject.toml`
- `package.json`
- `package-lock.json`
- statische Fallback-Version in `public/index.html`

#### Empfohlene Struktur auf dem Server

Beispiel für eine Subdomain wie `platzbelegung.sghochx.de`:

```text
/home/<user>/platzbelegung/
├── backend.php
├── config.yaml
├── data/
│   └── latest.json
└── public/
    ├── index.html
    ├── app.js
    └── style.css
```

#### Wichtiger Hinweis zu Shared Hosting

Die Weboberfläche selbst läuft mit statischen Dateien + PHP sehr gut auf klassischem Hosting. Der **Scraping-Teil** ist getrennt gedacht und kann bei Bedarf extern laufen. Genau deshalb ist `data/latest.json` das zentrale Austauschformat zwischen Scraper und Webserver.

#### Deploy per Skript (empfohlen)

Im Repo liegt ein Deploy-Skript, das die nötigen Dateien automatisch hochlädt, ohne echte Zugangsdaten ins Git zu legen.

1. Beispielkonfiguration kopieren:

```bash
cp deploy.example.env .deploy.local.env
```

2. `.deploy.local.env` lokal mit den echten Zugangsdaten füllen.

3. Deploy starten:

```bash
bash scripts/deploy.sh
```

Optional mit anderer Konfigurationsdatei:

```bash
bash scripts/deploy.sh /pfad/zu/meiner.deploy.env
```

#### Was das Skript macht

- führt optional `platzbelegung scrape` aus
- lädt `public/`, `backend.php` und `data/latest.json` hoch
- lädt optional zusätzlich `config.yaml`, `.htaccess` und `data/latest.html` hoch
- unterstützt `ftp`, `ftps`, `sftp` und `rsync`

#### Wichtige Dateien für das Skript

- `scripts/release.sh` → Release-Logik für Version, Tag und GitHub Release
- `scripts/deploy.sh` → Deploy-Logik
- `deploy.example.env` → commitbare Vorlage ohne echte Zugangsdaten
- `.deploy.local.env` → lokale Datei mit echten Zugangsdaten, wird nicht committed
- `.htaccess` → leitet Requests an `backend.php` weiter, damit `/` und `/api/...` auf klassischem Hosting funktionieren

## Projektstruktur

```
Platzbelegung/
├── config.yaml                        # Zentrale Konfiguration
├── README.md
├── pyproject.toml                     # Python-Paketdefinition
├── package.json                       # npm scripts (startet PHP-Server)
├── backend.php                         # PHP-Web-Server + API-Routen
├── public/                            # Statisches Frontend (Web-UI)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── src/
│   └── platzbelegung/
│       ├── __init__.py
│       ├── config.py                  # Lädt config.yaml
│       ├── scraper.py                 # Direkter fussball.de HTML-Scraper
│       ├── storage.py                 # JSON-Snapshot-Verwaltung
│       ├── models.py                  # Datenmodelle (ScrapedGame, OccupancySlot, …)
│       ├── parser.py                  # Spiele → Belegungsslots
│       ├── render_html.py             # Jinja2-HTML-Generierung
│       ├── display.py                 # Terminal-Ausgabe (rich)
│       ├── main.py                    # CLI-Einstiegspunkt
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
    └── (keine Node-Backend-Tests mehr)
```

## Tests

```bash
# Python
pytest

# (optional) npm script
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

## Hinweise

- Die App scrapt fussball.de; Änderungen im Layout können das Scraping beeinflussen.
- Beachte die Nutzungsbedingungen von fussball.de.
- `data/` ist gitignoriert – Snapshots werden lokal gespeichert.
