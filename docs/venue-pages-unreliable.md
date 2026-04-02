# Why Venue Pages Are Unreliable

## The Problem

Direct scraping of venue pages (`https://www.fussball.de/sportstaette/-/id/...`) has become unreliable for the following reasons:

### 1. Inconsistent HTML Structure

The HTML structure of venue pages changes frequently:
- Match rows may use different CSS classes (`table-striped`, `.match-row`, `.game-row`, etc.)
- Column order can vary
- Some pages use table layouts, others use div-based layouts
- JavaScript-rendered content may not be in the initial HTML

### 2. Incomplete Match Data

Venue pages don't always show all matches:
- Some games may be filtered out by default (e.g., youth games)
- Pagination is not always available or consistent
- Past games may be hidden after a certain time period
- Future games beyond a certain date may not be shown

### 3. Not Designed for Scraping

These pages are designed for human viewing, not programmatic access:
- No stable data attributes or IDs
- Content may be loaded asynchronously via JavaScript
- Anti-bot measures may be in place
- Rate limiting or blocking may occur

### 4. Breaking Changes

When fussball.de updates their website:
- HTML parsers break without warning
- New CSS classes or structure require code updates
- No version or API contract to rely on
- Manual testing and fixing required

## The Solution: ajax.club.matchplan

The club matchplan API provides:

### Stability
- More consistent data structure
- Less frequent changes
- Designed for data access (even if not officially public)

### Completeness
- All club games in one request
- Proper pagination support
- Includes all game types (home/away, all age groups)

### Maintainability
- Easier to parse (JSON or structured HTML)
- Clearer separation between data and presentation
- Fewer breaking changes

## Evidence

Common issues with venue-based scraping:

```python
# Issue 1: Missing matches
# Venue page shows: 3 games
# Club matchplan shows: 7 games (4 were filtered/hidden)

# Issue 2: Structure changes
# Before: <tr><td class="date">...</td></tr>
# After:  <div class="match-row"><span class="date">...</span></div>
# Result: Parser returns empty list

# Issue 3: JavaScript rendering
# Initial HTML: <div id="matches">Loading...</div>
# After JS:     <div id="matches"><table>...</table></div>
# Result: No matches found in initial HTML
```

## Recommendation

**Always prefer club matchplan API over venue pages.**

Only use venue-based scraping:
- As a temporary fallback during API outages
- For testing or debugging
- When explicitly needed for a specific use case

Mark any venue-based code as deprecated and log warnings when used.
