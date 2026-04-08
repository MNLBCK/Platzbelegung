# Issue: Mannschaftsgruppierung & Deduplizierung bei Spielgemeinschaften

## Datum
2026-04-07

## Problem
1. In der Mannschaftsübersicht werden Teams mit gleichem Namen/gleicher Altersklasse mehrfach aufgeführt, sobald sie in mehreren Wettbewerben (z. B. Liga und Pokal) spielen.
2. Beim Laden vorheriger/späterer Monate werden Spiele von Spielgemeinschaften (SG/SGM) mehrfach angezeigt.

## Erwartetes Verhalten
- Mannschaften werden nach **Teamname + Altersklasse** zusammengefasst.
- Bei mehreren Wettbewerben wird dies als Hinweis in der Spielklasse dargestellt (z. B. „mehrere Wettbewerbe“ mit Details).
- Beim Nachladen zusätzlicher Zeiträume werden identische Spiele robust dedupliziert.

## Umsetzung
- Frontend (`public/app.js`):
  - Team-Overview gruppiert nach Teamname und Altersklasse (aus Wettbewerb extrahiert).
  - Anzeige ergänzt um „mehrere Wettbewerbe“, wenn mehrere Wettbewerbe erkannt wurden.
  - Gemeinsame Deduplizierungslogik (`getGameDedupKey`, `dedupeGames`) für Initial- und Bereichs-Reload eingeführt.

## Akzeptanzkriterien
- Ein Team derselben Altersklasse erscheint nur einmal in der Mannschaftsliste.
- Bei mehreren Wettbewerben ist ein entsprechender Hinweis sichtbar.
- Beim Monatswechsel entstehen keine zusätzlichen Duplikate in der Spiel-Liste.
