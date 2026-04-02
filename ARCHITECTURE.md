# Platzbelegung – Architecture Documentation

## Data Source Strategy

### Primary: Club Matchplan API

The application primarily uses the **ajax.club.matchplan** API endpoint from fussball.de:

- **Endpoint**: `https://www.fussball.de/ajax.club.matchplan`
- **Parameters**:
  - `id`: Club ID (from fussball.de URL)
  - `saisonId`: Season code (optional, e.g., "2526" for 2025/26)
  - `loadmore`: Offset for pagination (added automatically)

**Why this is the primary source:**
- More stable API structure compared to HTML parsing
- Provides structured data (JSON or HTML fragments)
- Better pagination support
- Less prone to breaking when fussball.de changes their website

### Deprecated: Venue-based HTML Scraping

The old approach of scraping venue pages directly (`https://www.fussball.de/sportstaette/-/id/...`) is deprecated:

**Why it's deprecated:**
- HTML structure changes frequently
- Match rows are not reliably exposed anymore
- Harder to maintain
- Not designed for programmatic access

**When to use it:**
- Only as a fallback if the club matchplan API is unavailable
- Accessed via `--venue-id` CLI flag (shows deprecation warning)

## Data Flow

```
1. User runs: platzbelegung scrape

2. Scraper fetches club matchplan:
   GET /ajax.club.matchplan?id=CLUB_ID&saisonId=SEASON

3. Parser handles response (JSON or HTML fragment):
   - JSON: Extract from structured data
   - HTML: Parse match rows with selectors

4. Pagination loop:
   - If 20+ games in response, fetch next page
   - GET /ajax.club.matchplan?id=CLUB_ID&loadmore=OFFSET
   - Stop when empty response or limit reached

5. Filter by configured venues:
   - Keep only games where venue_id matches config.yaml

6. Save snapshot:
   - data/snapshots/{timestamp}.json
   - data/latest.json (symlink)
```

## Key Implementation Details

### Club Matchplan Scraper

**File**: `src/platzbelegung/scraper.py`

**Main method**: `FussballDeScraper.scrape_club_matchplan(club_id, season, limit)`

**Response handling**:
- Checks `Content-Type` header to determine JSON vs HTML
- JSON: `_parse_matchplan_json()` – extracts from structured data
- HTML: `_parse_matchplan_html()` – uses CSS selectors

**Pagination**:
- Automatic until empty response or limit reached
- Uses `loadmore` parameter with offset
- Typical page size: 20 games

### Venue Filtering

**Function**: `filter_games_by_venues(games, venue_ids)`

Filters the full club matchplan to only include games on configured venues. This allows:
- Monitoring multiple clubs' usage of the same venue
- Filtering out away games or games on other venues
- Flexible configuration without re-scraping

### CLI Integration

**File**: `src/platzbelegung/main.py`

**Behavior**:
- `platzbelegung scrape` → Uses club matchplan (default)
- `platzbelegung scrape --venue-id ID1 ID2` → Uses deprecated venue scraper (shows warning)

## Testing

**File**: `tests/test_scraper.py`

Tests cover:
- JSON response parsing
- HTML fragment parsing
- Pagination logic
- Venue filtering
- Backward compatibility with deprecated methods

## Future Considerations

### If ajax.club.matchplan becomes unavailable

1. Consider using the iste2 REST API wrapper (already supported via `legacy` command)
2. Could fall back to venue-based scraping with improved error handling
3. May need to implement rate limiting or more robust retry logic

### Potential Improvements

- **Caching**: Cache club matchplan responses to reduce API load
- **Incremental updates**: Only fetch new games since last scrape
- **Multi-club support**: Scrape multiple clubs' matchplans and merge results
- **Better error handling**: Distinguish between network errors, API changes, and empty results
- **Rate limiting**: Respect fussball.de's servers with request throttling

## Configuration

Relevant config.yaml sections:

```yaml
club:
  id: "CLUB_ID"      # Required for club matchplan scraping
  name: "Club Name"   # Optional, for display

season: "2526"       # Optional, defaults to current

venues:              # Optional, for filtering
  - id: "VENUE_ID_1"
    name: "Venue Name"
  - id: "VENUE_ID_2"
    name: "Another Venue"
```

## Migration Guide

If you're updating from the old venue-based scraping:

1. Ensure `club.id` is set in config.yaml
2. Remove `--venue-id` from any automation scripts
3. Run `platzbelegung scrape` without arguments
4. Verify the output includes all expected games
5. Update any documentation or runbooks

The old venue-based scraping is still available but deprecated. It will log warnings when used.
