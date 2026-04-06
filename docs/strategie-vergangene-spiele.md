# Strategie: Vergangene Spiele in der Platzbelegung anzeigen

## Ziel
Vergangene Spiele sollen so dargestellt werden, dass Platzverantwortliche schnell sehen:
1. **Was wurde gespielt?** (Ergebnis)
2. **Was fehlt noch?** (Spiel beendet, aber Ergebnis fehlt)
3. **Was kommt als Nächstes?** (aktuell geplanter Betrieb)

## Externe Referenzen (Kurzrecherche)

### fussball.de
- **Club Matchplan AJAX** wird im Projekt bereits genutzt (`/ajax.club.matchplan`) und liefert Zeitfenster-basiert Spiele inkl. Ergebnis-Feld, sofern vorhanden.
- Auf fussball.de gibt es zusätzlich **Widget-Ansätze** (Spielplan/Tabellen), die konzeptionell zeigen, dass Ergebnisdarstellung und Zeitfenster (Spieltag/Datum) getrennt steuerbar sind.

### Vergleichbares GitHub-Projekt
- Beispiel: `Davidsonity/Football_Fixtures-Scraper` arbeitet explizit mit der Trennung **"last five fixtures"** und **"next five fixtures"**.
- Diese Trennung ist für unsere Platzbelegung direkt übertragbar: „letzte Ergebnisse“ getrennt von „kommenden Spielen“.

## Empfohlene Produkt-Strategie

### 1) Vier Sektionen statt einer langen Liste
1. **Letzte Ergebnisse (z. B. 14 Tage)**
   - Absteigend sortiert (neueste oben)
   - Ergebnis prominent (z. B. Badge `2:1`)
2. **Heute / Kommend**
   - Aufsteigend sortiert
   - Fokus auf Planung / Platzbelegung
3. **Vergangen ohne Ergebnis**
   - Eigene Warnsektion („Ergebnis fehlt“)
   - Hilft Datenqualität und Nachpflege
4. **Archiv-Ergebnisse**
   - Älter als 14 Tage
   - Optional einklappbar

### 2) Einheitliche Erkennungslogik (regelbasiert)
- **Result vorhanden** (`result` nicht leer und nicht `-:-`) → Ergebnis-Spiel.
- **Kein Result, Start > jetzt - 3h** → kommend oder laufend.
- **Kein Result, Start <= jetzt - 3h** → vermutlich beendet, aber Ergebnis fehlt.

### 3) UX-Details
- Standardmäßig Sektion „Letzte Ergebnisse“ geöffnet, „Archiv“ zugeklappt.
- Filterchips: `Alle`, `Nur Ergebnisse`, `Nur Kommende`, `Ergebnis fehlt`.
- Auf Mobil: identische Logik, aber nur 2 initial sichtbare Sektionen (Ergebnisse + Kommend), Rest per Accordion.

## Prototypische Verifikation im Code

Prototyp implementiert in:
- `src/platzbelegung/past_games_strategy.py`
- `tests/test_past_games_strategy.py`

Der Prototyp validiert:
- korrekte Aufteilung in vier Sektionen,
- robustes Verhalten bei fehlerhaften Datumswerten,
- korrekte Sortierung der letzten Ergebnisse.

## Rollout-Vorschlag (inkrementell)
1. **Phase A (sicher):** Nur Logik + interne Auswertung (bereits prototypisch umgesetzt).
2. **Phase B:** UI-Sektion „Letzte Ergebnisse“ ergänzen (ohne bestehende Wochen-/Monatsansicht zu brechen).
3. **Phase C:** Warnsektion „Vergangen ohne Ergebnis“ + Admin-Hinweis für Datenqualität.
4. **Phase D:** Archiv-Performance optimieren (Pagination/Virtualisierung bei vielen Spielen).

## Risiken / Hinweise
- fussball.de liefert Ergebnisse nicht immer synchron zum Abpfiff; daher die 3h-„Grace Period“.
- Spielausfälle/Verlegungen sollten später explizit als eigener Status modelliert werden.
- Für Multi-Club-Betrieb ist die gleiche Logik nutzbar, nur Darstellung pro Verein/Platz differenzieren.
