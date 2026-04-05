# Team-/Gegnerlogo-Extraktion und automatisches Freistellen

## Übersicht

Die Platzbelegung-Anwendung extrahiert Team- und Vereinslogos aus fussball.de und zeigt diese in der Kalenderansicht und im Modal an. Dieses Dokument beschreibt die implementierte Strategie und Entscheidungen zur Logo-Extraktion und zum automatischen Freistellen.

## Logo-Quellen

### Primäre Quelle: Club-Matchplan HTML
Die Hauptquelle für Logos ist der Club-Matchplan von fussball.de:
- **URL**: `https://www.fussball.de/ajax.club.matchplan/-/id/{CLUB_ID}/...`
- **Vorteil**: Eine Anfrage liefert alle Spiele mit Logos
- **Nachteil**: Nicht alle Logos sind immer im HTML enthalten

### Sekundäre Quelle: Spiel-Detailseiten
Falls Logos im Matchplan fehlen, werden Spiel-Detailseiten nachgeladen:
- **URL**: `https://www.fussball.de/.../spiel/.../{GAME_ID}`
- **Vorteil**: Höhere Trefferquote für einzelne Spiele
- **Nachteil**: Zusätzliche HTTP-Anfragen erforderlich

### Tertiäre Quelle: fussball.de Logo-API
Wenn keine Bild-URLs extrahiert werden können, wird die offizielle Logo-API verwendet:
- **URL-Format**: `https://www.fussball.de/export.media/-/action/getLogo/format/7/id/{CLUB_ID}`
- **Vorteil**: Stabile, direkte URL wenn Club-/Team-ID bekannt
- **Nachteil**: Erfordert Extraktion der ID aus Links

## Extraktionsstrategie

### Backend (PHP) - `backend.php`

#### 1. Logo-Extraktion aus Club-Matchplan (`parseClubMatchplanHtml`)

Die Funktion `extractLogo` versucht in folgender Reihenfolge:

1. **Direktes `src`-Attribut**
   ```php
   $img = $xpath->evaluate('string(.//img[1]/@src)', $cell);
   ```

2. **Lazy-Load `data-src`-Attribut**
   ```php
   $img = $xpath->evaluate('string(.//img[1]/@data-src)', $cell);
   ```

3. **Responsive `srcset`-Attribut**
   ```php
   $srcset = $xpath->evaluate('string(.//img[1]/@srcset)', $cell);
   $img = preg_split('/\s+/', trim($srcset))[0] ?? '';
   ```

4. **Club-ID aus Links extrahieren**
   - Versucht mehrere Link-Muster:
     - `.club-wrapper` Container
     - `.club-name` Parent-Links
     - Links zu `/verein/` oder `/mannschaft/`
     - Generische erste Links
   - Extrahiert ID mit Regex: `~/id/([^/?#]+)~`
   - Konstruiert Logo-URL: `https://www.fussball.de/export.media/-/action/getLogo/format/7/id/{ID}`

#### 2. Logo-Extraktion aus Spiel-Details (`parseGameDetail`)

Verwendet folgende XPath-Selektoren in Prioritätsreihenfolge:

1. Team-Container (home/guest): `//*[contains(@class,"team") and contains(@class,"home")]//img[1]`
2. Club-Container (home/guest): `//*[contains(@class,"club") and contains(@class,"home")]//img[1]`
3. Generische getLogo-Bilder: `(//img[contains(@src,"getLogo") or contains(@data-src,"getLogo")])[1]`

**Verbesserte Fallback-Strategie**:
- Falls weniger als 2 Logos gefunden: Extraktion von Club-IDs aus Team/Club-Links
- Mehrere XPath-Ausdrücke für Team-Links (home/guest)
- Konstruktion von Logo-URLs aus extrahierten IDs

### Frontend (JavaScript) - `public/app.js`

#### Opponent-Logo-Erkennung (`getOpponentLogoUrl`)

Die Funktion bestimmt automatisch, welches Logo der Gegner ist:

1. Vergleich des aktuellen Club-Namens mit Home-/Gast-Team
2. Substring-Matching für Vereinsnamen ≥4 Zeichen
3. Word-basiertes Matching für kürzere/mehrteilige Namen
4. Fallback auf Gast-Logo

#### Logo-Anzeige

Logos werden an folgenden Stellen angezeigt:
- **Wochenansicht**: Game-Chips mit `.chip-logo`
- **Monatsansicht**: Liste mit `.gli-logo-img`
- **Game-Modal**: Detailansicht mit `.game-modal-team-logo`
- **Club-Suche**: Ergebnisse mit `.club-search-logo`
- **Letzte Clubs**: Quick-Select mit `.recent-club-logo`
- **Aktueller Club**: Header mit `.current-club-logo`

## Automatisches Freistellen

### Entscheidung: Client-seitige CSS-Lösung

Nach Evaluation der Optionen wurde eine **client-seitige CSS-Lösung** implementiert:

#### Evaluierte Optionen:

1. **Server-seitige Bildverarbeitung**
   - ❌ Komplex, erfordert Bildverarbeitungs-Bibliotheken (GD, ImageMagick)
   - ❌ Performance-Impact durch Bildverarbeitung
   - ❌ Zusätzlicher Speicher für verarbeitete Bilder

2. **Externe Services** (remove.bg, etc.)
   - ❌ Kosten für API-Nutzung
   - ❌ Abhängigkeit von Drittanbietern
   - ❌ Datenschutzbedenken

3. **Client-seitige CSS-Filter** ✅ **GEWÄHLT**
   - ✅ Keine zusätzliche Backend-Komplexität
   - ✅ Keine Performance-Kosten auf dem Server
   - ✅ Sofortige Anwendung ohne Wartezeit
   - ✅ Funktioniert gut für Logos mit weißem Hintergrund

### Implementierung

Alle Logo-Klassen verwenden folgende CSS-Eigenschaften:

```css
.chip-logo,
.game-modal-team-logo,
.gli-logo-img,
.club-search-logo,
.recent-club-logo,
.current-club-logo {
  /* Automatic background removal for logos with white backgrounds */
  filter: contrast(1.1) saturate(1.15);
  mix-blend-mode: multiply;
}
```

#### Wie es funktioniert:

1. **`mix-blend-mode: multiply`**
   - Weiße Pixel (RGB 255,255,255) werden transparent
   - Funktioniert wie Multiplizieren in Photoshop
   - Erhält Farbinformationen des Logos

2. **`filter: contrast(1.1) saturate(1.15)`**
   - Leichte Kontrasterhöhung macht Logo-Kanten schärfer
   - Sättigung kompensiert Farbverlust durch multiply
   - Subtile Anpassung, keine aggressive Veränderung

#### Vorteile:
- ✅ Funktioniert automatisch für alle Logos
- ✅ Keine zusätzlichen HTTP-Anfragen
- ✅ Keine Backend-Verarbeitung
- ✅ GPU-beschleunigt im Browser
- ✅ Funktioniert auch bei lazy-geladenen Bildern

#### Einschränkungen:
- ⚠️ Nur optimal für Logos mit weißem oder hellem Hintergrund
- ⚠️ Logos mit transparentem Hintergrund werden leicht verändert
- ⚠️ Sehr dunkle Hintergründe werden nicht vollständig entfernt

### Alternative für spezielle Fälle

Falls ein Logo-Freistellen nicht zufriedenstellend funktioniert, können Logos einzeln überschrieben werden:

```css
.chip-logo[src*="specific-club-id"] {
  mix-blend-mode: normal;
  filter: none;
}
```

## URL-Normalisierung

Alle extrahierten Logo-URLs werden durch `toAbsoluteUrl()` normalisiert:

```php
function toAbsoluteUrl(string $url): string
{
    if ($url === '') return '';
    if (str_starts_with($url, 'http')) return $url;      // Already absolute
    if (str_starts_with($url, '//')) return "https:$url"; // Protocol-relative
    if (str_starts_with($url, '/')) return FUSSBALL_DE_BASE . $url; // Domain-relative
    return $url;
}
```

## Error Handling

### Backend
- `try-catch` Blöcke bei HTTP-Anfragen
- Leere Strings bei fehlgeschlagener Extraktion
- Keine Fehler-Logs (Logos sind optional)

### Frontend
- `error`-Event-Listener auf `<img>`-Tags
- Entfernung fehlgeschlagener Bilder: `img.addEventListener('error', () => img.remove())`
- Fallback auf Text-Initial bei fehlenden Logos (Club-Suche)

## Caching

### Backend
- Keine explizite Caching-Schicht
- Logos werden bei jeder Matchplan-Anfrage neu extrahiert
- Browser-Caching von fussball.de-Ressourcen

### Frontend
- Session Storage für Game-Daten (inkl. Logo-URLs)
- Cookie-basiertes Caching für:
  - Aktueller Club (inkl. `logoUrl`)
  - Letzte Clubs (inkl. `logoUrl`)
- Browser-Caching von Logo-Bildern

## Performance-Optimierung

1. **Lazy Loading**
   - Alle Logo-`<img>`-Tags verwenden `loading="lazy"`
   - Reduziert initiale Ladezeit

2. **Parallele Detail-Anfragen**
   - Detail-Seiten werden nur bei fehlenden Logos geladen
   - Einzelne HTTP-Anfrage pro Game mit fehlendem Logo

3. **Deduplizierung**
   - `array_unique()` für extrahierte Logo-URLs
   - Verhindert doppelte Logos im Ergebnis

## Wartung und Updates

### Wenn fussball.de HTML ändert:

1. XPath-Selektoren in `parseGameDetail()` prüfen/anpassen
2. Neue CSS-Klassen zu Selektorliste hinzufügen
3. Logo-API-URL-Format validieren

### Wenn neue Logo-Anzeigepunkte hinzugefügt werden:

1. CSS-Klasse mit background-removal-Styles definieren
2. `loading="lazy"` und Error-Handler hinzufügen
3. `referrerpolicy="no-referrer"` bei externen Logos

## Zusammenfassung

**Gewählte Logo-Quellen**:
1. ✅ Club-Matchplan HTML (primär)
2. ✅ Spiel-Detailseiten (sekundär)
3. ✅ Logo-API mit ID-Extraktion (tertiär)

**Gewählte Freistell-Methode**:
- ✅ Client-seitige CSS-Filter (`mix-blend-mode: multiply`)
- ✅ Funktioniert automatisch für weiße Hintergründe
- ✅ Keine Server-Last, keine externen Services

**Resultat**:
- Robuste, mehrschichtige Logo-Extraktion
- Automatisches Freistellen ohne Performance-Impact
- Gute Trefferquote für Heim- und Gastteam-Logos
- Wartbare und erweiterbare Implementierung
