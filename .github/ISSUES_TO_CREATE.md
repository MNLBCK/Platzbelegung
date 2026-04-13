# Issues to Create – Platzbelegung

This file contains the canonical texts for 12 project-improvement issues.
Use `scripts/create_issues.py` to create them automatically (see README).

---

## Issue 1

**Titel:** Vereinheitlichung der Parsing-Logik in Python und PHP

**Labels:** `refactor`, `enhancement`

**Beschreibung:**

Aktuell wird Matchplan-/Spiel-Parsing sowohl in `src/platzbelegung/scraper.py` als auch in `backend.php` umgesetzt. Das erhöht Wartungsaufwand und Fehleranfälligkeit bei Änderungen an fussball.de.

### Ziel

* Eine einzige Source of Truth für Parsing und Normalisierung definieren
* PHP-Backend auf Snapshot-Auslieferung bzw. schlanke API-Logik reduzieren
* Doppelte Datums-, Venue- und Matchplan-Parser entfernen

### Akzeptanzkriterien

* Parsing fachlicher Spieldaten liegt nur noch in einer Schicht
* Keine doppelte HTML-Parsing-Logik mehr in Python und PHP
* Bestehende Tests laufen weiter oder werden angepasst
* Dokumentation im README aktualisiert

### Betroffene Dateien

* `src/platzbelegung/scraper.py`
* `backend.php`

---

## Issue 2

**Titel:** Konfigurationszugriff ohne Python-Shell-Aufrufe aus PHP umbauen

**Labels:** `refactor`, `enhancement`

**Beschreibung:**

`backend.php` liest und schreibt `config.yaml` aktuell über `python3 -c ...`-Aufrufe. Das koppelt das Web-Backend unnötig an Python und PyYAML.

### Ziel

* Konfigurationszugriff vereinfachen und robuster machen
* Shell-Aufrufe aus PHP für Config-Lesen/Schreiben entfernen
* Gemeinsamen Konfigurationsvertrag definieren, z. B. JSON für Web-seitige Schreibzugriffe

### Akzeptanzkriterien

* Kein `shell_exec`/`exec` mehr für Config-Handling in PHP
* Fehlerfälle sauber behandelt
* Deployment ohne implizite Python-Abhängigkeit für reine Web-Nutzung möglich
* README aktualisiert

### Betroffene Dateien

* `backend.php`
* `src/platzbelegung/config.py`
* `README.md`

---

## Issue 3

**Titel:** Hardening der PHP-API für Suche, Admin-Endpunkte und Config-Änderungen

**Labels:** `security`, `enhancement`

**Beschreibung:**

Mehrere Endpunkte ziehen externe Inhalte, speichern Konfiguration oder schützen Admin-Daten nur per Passwort im Query-String. Das sollte robuster und sicherer werden.

### Ziel

* Query-String-Passwort für Admin-Endpunkt ablösen oder absichern
* Logging/Audit für Schreibzugriffe ergänzen
* Rate Limiting bzw. Schutz vor Missbrauch für Such-/Matchplan-Endpunkte vorbereiten
* Fehlerbilder intern besser unterscheidbar machen

### Akzeptanzkriterien

* Admin-Zugriff nicht mehr ausschließlich über Passwort im Query-String
* Schreibzugriffe auf `/api/config/*` nachvollziehbar protokolliert
* Externe Requests haben saubere Fehlerbehandlung
* Technische Fehler werden intern differenziert geloggt

### Betroffene Dateien

* `backend.php`

---

## Issue 4

**Titel:** Versioniertes Snapshot-Schema für `latest.json` einführen

**Labels:** `enhancement`, `refactor`

**Beschreibung:**

`data/latest.json` ist das zentrale Austauschformat zwischen Scraper, HTML-Generator und Web-UI. Aktuell fehlt ein explizit versioniertes Schema.

### Ziel

* `schemaVersion` im Snapshot ergänzen
* Datenvertrag für `games`, Meta-Felder und optionale Felder dokumentieren
* Vorbereitung für zukünftige Erweiterungen wie Logos, Resultate, zusätzliche Venue-Metadaten

### Akzeptanzkriterien

* Snapshot enthält Schema-Version
* Konsumenten prüfen oder tolerieren die Version
* README dokumentiert Format und Migrationsstrategie
* Abwärtskompatibilität bewusst geregelt

### Betroffene Dateien

* `README.md`
* `storage.py`
* `backend.php`
* Frontend-Konsumenten von Snapshot-Daten

---

## Issue 5

**Titel:** Einheitliches Datums- und Zeitzonenmodell im gesamten Projekt

**Labels:** `enhancement`, `refactor`

**Beschreibung:**

Es gibt aktuell gemischte Formate mit lokalen Datumswerten, ISO-Strings und teils UTC-Timestamps. Das ist funktional, aber inkonsistent.

### Ziel

* Einheitliches internes Zeitformat definieren
* ISO-8601 mit klarer Zeitzonenstrategie verwenden
* UI-Formatierung strikt von Speicher-/Transportformat trennen

### Akzeptanzkriterien

* `startDate`/`generated_at`/`scraped_at` sind konsistent dokumentiert
* Python und PHP erzeugen kompatible Zeitwerte
* Sortierung und Anzeige bleiben korrekt
* Tests decken Randfälle ab

### Betroffene Dateien

* `src/platzbelegung/scraper.py`
* `src/platzbelegung/parser.py`
* `backend.php`

---

## Issue 6

**Titel:** `public/app.js` modularisieren und Verantwortlichkeiten trennen

**Labels:** `refactor`, `enhancement`

**Beschreibung:**

`public/app.js` bündelt State, Storage, API-Zugriffe, Kalender-Rendering, Clubsuche, SG-Erkennung und Modal-UI in einer großen Datei. Das erschwert Wartung und Testing.

### Ziel

* Datei in sinnvolle Module aufteilen
* Verantwortlichkeiten trennen, z. B. `state`, `api`, `calendar`, `clubs`, `venues`, `ui`
* Grundlage für bessere Tests und kleinere Änderungen schaffen

### Akzeptanzkriterien

* `app.js` ist deutlich kleiner oder nur noch Einstiegspunkt
* Kein Verlust bestehender Funktionen
* Initialisierung und State-Fluss sind nachvollziehbarer
* Browser-kompatibler Build-freier Ansatz oder bewusstes Build-Setup dokumentiert

### Betroffene Dateien

* `public/app.js`

---

## Issue 7

**Titel:** Clientseitige Persistenz konsolidieren

**Labels:** `refactor`, `enhancement`

**Beschreibung:**

Der Frontend-State wird aktuell gemischt in Cookies und `sessionStorage` gehalten. Das sollte sauberer getrennt werden.

### Ziel

* Persistenzkonzept definieren
* UI-Präferenzen und Session-Daten klar trennen
* Cookies nur verwenden, wenn sie serverseitig wirklich nötig sind

### Akzeptanzkriterien

* Dokumentiertes Persistenzmodell
* Weniger Cookie-Abhängigkeit
* Bestehende Features wie letzte Vereine, Venue-Filter und View-State bleiben erhalten
* Migration bestehender gespeicherter Werte bedacht

### Betroffene Dateien

* `public/app.js`

---

## Issue 8

**Titel:** Testabdeckung nach PHP-Migration für API und Frontend ausbauen

**Labels:** `testing`, `enhancement`

**Beschreibung:**

Python-Tests sind vorhanden, aber für das PHP-Backend und das Frontend fehlt weitgehend automatisierte Absicherung.

### Ziel

* Kritische API-Endpunkte testen
* Zentrale Frontend-Logik testbar machen
* Regressionsschutz für Venue-Filter, SG-Erkennung, Deduplizierung und Kalenderansichten erhöhen

### Akzeptanzkriterien

* Automatisierte Tests für zentrale API-Endpunkte vorhanden
* Mindestens Kernlogik im Frontend testbar
* `npm test` ist nicht mehr nur ein Placeholder
* Teststrategie im README oder CONTRIBUTING beschrieben

### Betroffene Dateien

* `package.json`
* `backend.php`
* `public/app.js`
* `tests/`

---

## Issue 9

**Titel:** CI-Pipeline für Tests, Linting und Konsistenzprüfungen ergänzen

**Labels:** `ci`, `enhancement`

**Beschreibung:**

Das Repo kombiniert Python, PHP und statisches Frontend. Eine kleine CI würde Fehler früh sichtbar machen.

### Ziel

* Automatische Testausführung bei PRs
* Syntax-/Lint-Checks für Python und PHP
* Optionale Konsistenzchecks für Versionsnummern und Doku

### Akzeptanzkriterien

* CI läuft bei Push/PR
* Python-Tests werden ausgeführt
* PHP-Syntax wird geprüft
* Fehlerhafte Änderungen blockieren frühzeitig

### Betroffene Dateien

* GitHub Actions Workflow
* `pyproject.toml`
* `package.json`

---

## Issue 10

**Titel:** Spieldauer-Regeln robuster und expliziter modellieren

**Labels:** `enhancement`, `refactor`

**Beschreibung:**

Die Belegungsdauer wird aktuell per Text-Matching auf `competition` ermittelt. Das ist pragmatisch, aber fragil.

### Ziel

* Regelwerk für Spieldauern expliziter machen
* Konfigurierbare Prioritäten und Overrides ermöglichen
* Weniger Abhängigkeit von freien Texten in Wettbewerbsnamen

### Akzeptanzkriterien

* Dauerlogik ist nachvollziehbar und testbar
* Konfiguration für Sonderfälle möglich
* Parser bleibt kompatibel mit bestehenden Daten
* Randfälle sind durch Tests abgedeckt

### Betroffene Dateien

* `src/platzbelegung/parser.py`
* `src/platzbelegung/config.py`

---

## Issue 11

**Titel:** Strukturierte Fehlerbehandlung und Logging für Scraper und Backend

**Labels:** `enhancement`, `logging`

**Beschreibung:**

Mehrere Fehlerpfade geben nur generische Meldungen zurück. Für Betrieb, Diagnose und Wartung wären strukturiertere Fehler hilfreich.

### Ziel

* Interne Fehlercodes oder Kategorien definieren
* Upstream-/Netzwerk-/Parsingfehler klar unterscheiden
* Nutzerfreundliche Meldungen von internem Logging trennen

### Akzeptanzkriterien

* Logging enthält mehr Kontext
* HTTP-Fehlerpfade sind konsistent
* Nutzer bekommen verständliche Meldungen
* Entwickler können Ursachen leichter nachvollziehen

### Betroffene Dateien

* `src/platzbelegung/scraper.py`
* `backend.php`

---

## Issue 12

**Titel:** Lizenz- und Versionsangaben im Repo vereinheitlichen

**Labels:** `maintenance`, `enhancement`

**Beschreibung:**

Aktuell ist im Python-Paket MIT hinterlegt, in `package.json` jedoch ISC. Außerdem wird Version an mehreren Stellen geführt.

### Ziel

* Einheitliche Lizenzangabe im gesamten Repo
* Klare Single Source of Truth für Versionen
* Release-Metadaten konsistent ableiten

### Akzeptanzkriterien

* Keine widersprüchlichen Lizenzangaben mehr
* Versionsquelle ist dokumentiert
* Build-/Release-Meta folgt konsistent daraus

### Betroffene Dateien

* `pyproject.toml`
* `package.json`
* `backend.php` / `VERSION` / `BUILD_META.json`
