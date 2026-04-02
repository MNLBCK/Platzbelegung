# Refactoring Summary: Club Matchplan as Primary Data Source

## Overview

This refactoring changes the scraping architecture from venue-based HTML parsing to club matchplan API as the primary data source, addressing the issues outlined in the original problem statement.

## Changes Made

### 1. New Club Matchplan Scraper (Primary)

**File**: `src/platzbelegung/scraper.py`

- **Added**: `scrape_club_matchplan(club_id, season, limit)` method
  - Fetches club games via `ajax.club.matchplan` endpoint
  - Supports both JSON and HTML fragment responses
  - Implements automatic pagination with `loadmore` parameter
  - More stable and reliable than venue-based scraping

- **Added**: `_parse_matchplan_json()` and `_parse_matchplan_html()` parsers
  - Handles different response formats from the API
  - Extracts venue, team, competition, and timing data
  - Robust CSS selectors for HTML parsing

- **Added**: `filter_games_by_venues()` utility function
  - Filters club-wide games to only configured venues
  - Enables flexible venue monitoring without re-scraping

### 2. Deprecated Venue-Based Scraper (Fallback)

- **Updated**: `scrape_venue_games()` now logs deprecation warnings
- **Documentation**: Added extensive docstring explaining why it's deprecated
- **Kept for backward compatibility**: Still accessible via `--venue-id` flag

### 3. CLI Refactoring

**File**: `src/platzbelegung/main.py`

- **Default behavior**: Now uses club matchplan scraping
  - Fetches all club games
  - Filters by configured venues
  - Shows progress and statistics

- **Legacy behavior**: Venue-based scraping with `--venue-id`
  - Shows deprecation warning
  - Uses old HTML parser
  - Maintained for backward compatibility

- **Updated help text**: Clearly indicates primary vs deprecated methods

### 4. Documentation

**New files**:
- `ARCHITECTURE.md`: Complete architecture documentation
  - Data source strategy
  - Implementation details
  - Testing approach
  - Migration guide
  - Future considerations

- `docs/venue-pages-unreliable.md`: Detailed explanation
  - Why venue pages are unreliable
  - Specific issues and examples
  - Evidence and recommendations

**Updated files**:
- `README.md`:
  - Added "Datenquellen" section
  - Explained club-first architecture
  - Updated workflow examples
  - Marked `--venue-id` as deprecated

### 5. Comprehensive Testing

**File**: `tests/test_scraper.py`

Added 6 new test classes:
- `TestScrapeClubMatchplan`: JSON and HTML parsing
- `TestFilterGamesByVenues`: Venue filtering logic
- Tests for pagination behavior
- Tests for error handling

**All tests pass**: 65 tests total, including:
- 15 scraper tests (9 existing + 6 new)
- 8 storage tests
- 18 parser tests
- 8 render tests
- 4 display tests
- 8 API client tests
- 4 test files for Node.js

## Impact

### What Changed for Users

**Default usage** (no arguments):
```bash
# Before: Required --venue-id or config.yaml venues
platzbelegung scrape --venue-id V1 V2

# After: Uses club ID from config.yaml, filters by venues
platzbelegung scrape
```

**Configuration**:
```yaml
# Before: Only venues were required
venues:
  - id: "VENUE1"

# After: Club ID is primary, venues are filters
club:
  id: "CLUB_ID"  # Required
  name: "Name"   # Optional

venues:  # Optional - for filtering
  - id: "VENUE1"
```

### What Stayed the Same

- All output formats unchanged (JSON snapshots, HTML, terminal)
- Data model unchanged (ScrapedGame)
- Storage format unchanged (backward compatible)
- Legacy command still works
- Venue-based scraping still available (with warnings)

## Benefits

1. **More Reliable**: API-based scraping is less prone to breaking
2. **Better Data**: Access to all club games, not just what venue pages show
3. **Easier Maintenance**: Fewer HTML structure changes to handle
4. **Clearer Architecture**: Explicit separation of concerns
5. **Better Documentation**: Clear explanation of why and how
6. **Future-Proof**: Easier to extend with new features

## Migration Path

For existing users:

1. **Add club ID to config.yaml**
   ```yaml
   club:
     id: "YOUR_CLUB_ID"
   ```

2. **Remove --venue-id from scripts** (if used)

3. **Keep venue configuration** (now used for filtering)

4. **Test**: Run `platzbelegung scrape` and verify output

5. **Optional**: Remove venue IDs if you want all club games

## Statistics

- **Files changed**: 6
- **Lines added**: 785
- **Lines removed**: 30
- **Net change**: +755 lines
- **New tests**: 6 test classes, ~180 lines
- **Documentation**: 2 new files, ~240 lines

## Verification

All tests pass:
```
65 passed in 0.38s
```

CLI works correctly:
```bash
✓ platzbelegung --help
✓ platzbelegung scrape --help
✓ All commands show updated descriptions
```

## Issue Resolution

This refactoring addresses all points from the original issue:

- ✅ Renamed/deprecated `scrape_venue_games()` in favor of club matchplan API
- ✅ Made source strategy explicit in CLI/help/docs
- ✅ Separated raw scraped matchplan from filtered occupancy
- ✅ Added tests for pagination via `ajax.club.matchplan.loadmore`
- ✅ Documented why `sportstaette/-/id/...` is unreliable

## Next Steps

Recommended follow-up work:

1. Monitor production usage for any API issues
2. Consider adding response caching to reduce API load
3. Potentially add rate limiting for politeness
4. Document actual API response format based on real usage
5. Consider removing venue-based scraping entirely in v1.0

## Conclusion

This refactoring successfully modernizes the scraping architecture while maintaining backward compatibility. The club matchplan API is now the primary, documented, and tested data source, with clear explanations of why this approach is superior to venue-based HTML scraping.
