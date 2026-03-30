# Platzbelegung

Durchsucht online Quellen (vorrangig fussball.de) nach Spielen auf einem oder mehreren bestimmten Sportplätzen, und stellt die Platzbelegung übersichtlich dar.

## Projektbeschreibung

**Platzbelegung** liest Spielplandaten von [fussball.de](https://www.fussball.de) über eine lokale REST-API aus und stellt die Belegung aller Sportstätten eines Vereins übersichtlich im Terminal dar.

Ein Verein kann **mehrere Mannschaften** (Herren, A-Jugend, B-Jugend, …) haben und diese können **mehrere Sportstätten** (Kunstrasenplatz, Rasenplatz, Bezirkssportanlage, …) nutzen.  
Die Belegungsübersicht zeigt für jede Sportstätte, an welchen Tagen welche Mannschaft spielt – inklusive Auf- und Abbauzeit (15 Minuten Puffer vor dem Anstoß).

## Voraussetzungen

- Python 3.10 oder neuer
- Eine laufende Instanz der [fussball.de REST API von iste2](https://github.com/iste2/Fu-ball.de-REST-API)
  - Standardmäßig wird `http://localhost:5000` erwartet

## Installation

```bash
# Abhängigkeiten installieren (im Editable-Modus)
pip install -e ".[dev]"
```

## Nutzung

```bash
# Standardkonfiguration (SKV Hochberg, aktuelle Saison)
platzbelegung

# Eigene Vereins-ID und API-URL
platzbelegung --club-id 00ES8GNAVO00000PVV0AG08LVUPGND5I --api-url http://localhost:5000

# Andere Saison
platzbelegung --season 2425

# Detaillierte Ausgabe
platzbelegung --verbose
```

## Konfiguration

Die Standardkonfiguration befindet sich in `src/platzbelegung/config.py`:

| Variable        | Beschreibung                         | Standard                           |
|-----------------|--------------------------------------|------------------------------------|
| `CLUB_ID`       | Vereins-ID aus der fussball.de-URL   | `00ES8GNAVO00000PVV0AG08LVUPGND5I` |
| `API_BASE_URL`  | Basis-URL der REST API               | `http://localhost:5000`            |
| `SEASON`        | Saison-Code (z.B. `2526` = 2025/26)  | `2526`                             |

Der abgefragte Zeitraum umfasst dynamisch den **aktuellen Monat** sowie den **Monat, der in 3 Wochen liegt** (kann der gleiche oder der nächste Monat sein).

## Projektstruktur

```
Platzbelegung/
├── README.md                    # Diese Datei
├── pyproject.toml               # Projektdefinition und Abhängigkeiten
├── src/
│   └── platzbelegung/
│       ├── __init__.py
│       ├── main.py              # CLI-Einstiegspunkt
│       ├── config.py            # Konfiguration
│       ├── models.py            # Datenmodelle: Team, Game, Venue, OccupancySlot
│       ├── api_client.py        # HTTP-Client für die fussball.de REST API
│       ├── parser.py            # Logik: Spiele → Platzbelegung
│       └── display.py           # Tabellarische Ausgabe (rich)
└── tests/
    ├── __init__.py
    ├── test_api_client.py
    ├── test_parser.py
    └── test_display.py
```

## Architektur

```
CLI (main.py)
    │
    ├── FussballDeApiClient (api_client.py)
    │       └── fussball.de REST API  [extern]
    │
    ├── games_to_occupancy (parser.py)
    │       ├── extract_venue()
    │       ├── group_by_venue()
    │       └── group_by_date()
    │
    └── display_occupancy (display.py)
            └── rich Terminal-Tabellen
```

## Tests

```bash
pytest
```

## Datenquelle

Die Daten werden über die Open-Source REST API
[iste2/Fu-ball.de-REST-API](https://github.com/iste2/Fu-ball.de-REST-API)
abgerufen, die fussball.de scrapt. Diese muss lokal laufen und unter der
konfigurierten `API_BASE_URL` erreichbar sein.

## Beispiel-Ausgabe

```
Platzbelegung – Verein: 00ES8GNAVO00000PVV0AG08LVUPGND5I  Zeitraum: 01.03.2026 – 30.04.2026

Mannschaften (3):
  • SKV Hochberg – Herren (Herren)
  • SKV Hochberg – A-Junioren (A-Junioren)
  • SKV Hochberg – B-Junioren (B-Junioren)

 ══════════════════════════════════════════════════════════════════
 📍 Kunstrasenplatz, Sportanlage Hochberg, Hauptstr. 1, 70000 Stuttgart
 ══════════════════════════════════════════════════════════════════

  📅 Samstag, 15. März 2026

   Von    Bis    Mannschaft         Art          Gegner           Liga
   10:45  12:15  SKV Hochberg       Herren       FC Muster        Kreisliga A
   14:45  16:15  SKV Hochberg II    Herren       SV Beispiel      Kreisliga B
```
