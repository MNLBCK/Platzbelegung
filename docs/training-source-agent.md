# Arbeitsanweisung Fuer Eine KI: Trainingsquellen Auf Webseiten Pruefen

## Ziel

Die Anwendung verwaltet Trainingsquellen in `data/training_sources.json`.
Jede Quelle enthaelt mindestens:

- `club_name`
- `team`
- `source_url`

Deine Aufgabe ist es, fuer jede hinterlegte `source_url` die Website zu oeffnen, die dort veroeffentlichten Trainingszeiten zu verstehen und das Ergebnis so zu dokumentieren, dass ein Entwickler oder eine weitere KI daraus direkt Parser-Logik oder strukturierte Trainingsdaten ableiten kann.

## Was Du Auf Der Website Tun Sollst

1. Oeffne die `source_url`.
2. Pruefe, ob auf der Seite tatsaechlich Trainingszeiten stehen oder ob die Seite nur ein Einstieg ist.
3. Wenn noetig, folge intern genau den Links oder Tabs, die offensichtlich zu den Trainingszeiten fuehren.
   Beispiele:
   - `Trainingszeiten`
   - `Trainingsplan`
   - `Mannschaften`
   - `Junioren`
   - PDF-Downloads mit Trainingsplan
4. Ignoriere Inhalte, die keine regulaeren Trainingszeiten sind.
   Beispiele:
   - News
   - Spielberichte
   - einmalige Termine
   - Turniere
   - Spielplaene
5. Suche gezielt nach wiederkehrenden Trainingseinheiten und erfasse pro Einheit:
   - `club_name`
   - `team_name`
   - `weekday` mit Mapping `0=Montag`, `1=Dienstag`, `2=Mittwoch`, `3=Donnerstag`, `4=Freitag`, `5=Samstag`, `6=Sonntag`
   - `start_time` im Format `HH:MM`
   - `end_time` im Format `HH:MM`, falls explizit angegeben
   - `venue_name`, falls auf der Seite erkennbar
   - `source_url` der konkreten Seite, auf der die Information gefunden wurde
6. Falls Zeiten nicht explizit als strukturierte Tabelle vorliegen, pruefe auch:
   - Listen
   - Freitextabschnitte
   - eingebettete Dokumente
   - Akkordeons
   - Tabs
   - mobile Varianten derselben Seite
7. Wenn die Quelle unklar oder unvollstaendig ist, halte das explizit fest statt zu raten.

## Wichtige Regeln

- Rate keine Trainingszeiten.
- Uebernimm nur Informationen, die auf der Website klar erkennbar sind.
- Vermische keine Spielzeiten mit Trainingszeiten.
- Wenn eine Seite mehrere Teams enthaelt, dokumentiere jede Trainingseinheit separat.
- Wenn eine Zeitspanne fehlt, notiere das als fehlend statt eine Endzeit zu erfinden.
- Wenn mehrere Sportstaetten genannt werden, ordne `venue_name` nur dann zu, wenn die Zuordnung zur Einheit klar ist.
- Wenn eine URL auf eine andere Zielseite oder auf ein PDF weiterleitet, dokumentiere die tatsaechlich verwendete Zielquelle.

## Wie Du Das Ergebnis Dokumentieren Sollst

Lege fuer jede bearbeitete Quelle einen Abschnitt in einer Markdown-Datei an. Empfohlener Dateiname:

`docs/training-source-review.md`

Verwende pro Quelle genau dieses Schema:

```md
## Quelle: <club_name> - <team>

- Eingangs-URL: <source_url aus data/training_sources.json>
- Gepruefte Ziel-URL: <finale Seite oder PDF>
- Status: `ok` | `teilweise` | `keine_trainingszeiten` | `blockiert`
- Kurzfazit: <1-3 Saetze>

### Gefundene Trainingszeiten

| club_name | team_name | weekday | start_time | end_time | venue_name | source_url |
|---|---|---:|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... |

### Parser-Hinweise

- Seitentyp: `tabelle` | `liste` | `freitext` | `pdf` | `sonstiges`
- Relevante Ueberschriften / Labels: ...
- Relevante Struktur oder Selektoren: ...
- Besonderheiten: ...

### Offene Punkte

- ...
```

## Wie Du Den Status Vergibst

- `ok`
  Die Trainingszeiten sind klar erkennbar und koennen weitgehend eindeutig extrahiert werden.
- `teilweise`
  Ein Teil ist brauchbar, aber einzelne Angaben fehlen oder sind mehrdeutig.
- `keine_trainingszeiten`
  Auf der Quelle sind keine verwertbaren regulaeren Trainingszeiten zu finden.
- `blockiert`
  Die Quelle ist ohne weitere Hilfe nicht auswertbar.
  Beispiele:
  - Login erforderlich
  - nur Bild ohne lesbaren Text
  - kaputter Link
  - Datei nicht erreichbar

## Was In "Parser-Hinweise" Stehen Soll

Ziel der Parser-Hinweise ist nicht eine allgemeine Beschreibung, sondern konkrete Hilfe fuer die technische Extraktion.

Nenne dort insbesondere:

- ob die Daten in einer Tabelle, Liste oder in Freitext stehen
- welche Ueberschriften die Trainingssektion markieren
- ob Teamname, Wochentag, Uhrzeit und Ort in getrennten Spalten oder gemischt im Text stehen
- ob Sonderlogik noetig ist
  Beispiele:
  - mehrere Teams in einer Zeile
  - ein Team als Zwischenueberschrift, darunter mehrere Zeiten
  - Ort nur in einer uebergeordneten Sektion sichtbar
  - PDF statt HTML

## Wie Du Deine Arbeit Abschliessen Sollst

1. Stelle sicher, dass jede bearbeitete Quelle einen vollstaendigen Abschnitt in `docs/training-source-review.md` hat.
2. Schreibe am Ende der Datei eine kurze Zusammenfassung:

```md
## Gesamtfazit

- Bearbeitete Quellen: <Anzahl>
- Davon `ok`: <Anzahl>
- Davon `teilweise`: <Anzahl>
- Davon `keine_trainingszeiten`: <Anzahl>
- Davon `blockiert`: <Anzahl>
- Empfohlene naechste Schritte:
  - ...
```

3. Wenn eine Quelle technisch gut parsebar ist, formuliere in `Parser-Hinweise` so konkret, dass daraus direkt Code entstehen kann.
4. Wenn eine Quelle nicht parsebar ist, beschreibe den Blocker klar und knapp.
5. Beende die Arbeit erst, wenn fuer jede hinterlegte URL ein dokumentiertes Ergebnis oder ein klarer Blocker vorliegt.

## Nicht Tun

- Keine stillschweigenden Annahmen treffen.
- Keine Daten direkt in `data/latest.json` oder Snapshots schreiben.
- Keine Trainingsquellen loeschen oder ueberschreiben, nur weil die Seite unklar ist.
- Keine "vermutlichen" Trainingszeiten dokumentieren.
