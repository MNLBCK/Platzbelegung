'use strict';

const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const NodeCache = require('node-cache');
const path = require('path');

const app = express();
const cache = new NodeCache({ stdTTL: 300 }); // 5 min cache

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const FUSSBALL_DE_BASE = 'https://www.fussball.de';

const HTTP_HEADERS = {
  'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'de-DE,de;q=0.9,en;q=0.5',
  'Accept-Encoding': 'gzip, deflate, br',
  Connection: 'keep-alive',
};

/**
 * Parse a German date/time string from fussball.de
 * Typical formats: "28.03.2026 14:00" or "28.03.2026"
 * @param {string} dateStr
 * @param {string} timeStr
 * @returns {Date|null}
 */
function parseGermanDate(dateStr, timeStr) {
  if (!dateStr) return null;
  const match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{4})/);
  if (!match) return null;
  const [, day, month, year] = match;
  const timeMatch = timeStr && timeStr.match(/(\d{2}):(\d{2})/);
  const hours = timeMatch ? parseInt(timeMatch[1], 10) : 0;
  const minutes = timeMatch ? parseInt(timeMatch[2], 10) : 0;
  return new Date(
    parseInt(year, 10),
    parseInt(month, 10) - 1,
    parseInt(day, 10),
    hours,
    minutes
  );
}

/**
 * Scrape games for a venue from fussball.de
 * @param {string} venueId - fussball.de venue (Sportstätte) ID
 * @returns {Promise<Array>} Array of game objects
 */
async function scrapeVenueGames(venueId) {
  const cacheKey = `venue_${venueId}`;
  const cached = cache.get(cacheKey);
  if (cached) return cached;

  const url = `${FUSSBALL_DE_BASE}/sportstaette/-/id/${encodeURIComponent(venueId)}`;

  const response = await axios.get(url, {
    headers: HTTP_HEADERS,
    timeout: 15000,
    maxContentLength: 10 * 1024 * 1024, // 10 MB limit
  });

  const $ = cheerio.load(response.data);
  const games = [];

  // Extract venue name from the page title/header
  const venueName =
    $('h1.headline').first().text().trim() ||
    $('h2.headline').first().text().trim() ||
    $('title').text().replace(/fussball\.de/g, '').replace(/\|/g, '').trim() ||
    `Platz ${venueId}`;

  // fussball.de renders game rows in tables with class "table-thead-row" for headers
  // and individual game rows
  $('table.table-striped tbody tr, .result-set-row').each((_, row) => {
    const cells = $(row).find('td');
    if (cells.length < 4) return;

    const dateText = $(cells[0]).text().trim();
    const timeText = $(cells[1]).text().trim();
    const homeTeam = $(cells[2]).text().trim();
    const guestTeam = $(cells[4]).text().trim();
    const competition = $(cells[5]).text().trim();

    if (!dateText || !homeTeam) return;

    const startDate = parseGermanDate(dateText, timeText);
    if (!startDate) return;

    games.push({
      venueId,
      venueName,
      date: dateText,
      time: timeText,
      homeTeam,
      guestTeam,
      competition,
      startDate: startDate.toISOString(),
    });
  });

  // Alternative selector for different page layouts
  if (games.length === 0) {
    $('.fixture-list-item, .match-row, .game-row').each((_, item) => {
      const dateText =
        $(item).find('.date, .match-date').text().trim();
      const timeText =
        $(item).find('.time, .match-time').text().trim();
      const homeTeam =
        $(item).find('.home-team, .team-home').text().trim();
      const guestTeam =
        $(item).find('.guest-team, .team-guest').text().trim();
      const competition =
        $(item).find('.competition, .league').text().trim();

      if (!dateText || !homeTeam) return;

      const startDate = parseGermanDate(dateText, timeText);
      if (!startDate) return;

      games.push({
        venueId,
        venueName,
        date: dateText,
        time: timeText,
        homeTeam,
        guestTeam,
        competition,
        startDate: startDate.toISOString(),
      });
    });
  }

  cache.set(cacheKey, games);
  return games;
}

/**
 * Search fussball.de for venues by name
 * @param {string} query - search term
 * @returns {Promise<Array>} Array of venue objects {id, name, location}
 */
async function searchVenues(query) {
  const cacheKey = `search_${query}`;
  const cached = cache.get(cacheKey);
  if (cached) return cached;

  const url = `${FUSSBALL_DE_BASE}/suche/-/suche/${encodeURIComponent(query)}/typ/sportstaette`;

  const response = await axios.get(url, {
    headers: HTTP_HEADERS,
    timeout: 15000,
    maxContentLength: 5 * 1024 * 1024, // 5 MB limit
  });

  const $ = cheerio.load(response.data);
  const venues = [];

  // Parse search results
  $('.search-result-item, .result-item').each((_, item) => {
    const link = $(item).find('a').first();
    const href = link.attr('href') || '';
    const name = link.text().trim() || $(item).find('.title').text().trim();
    const location = $(item).find('.location, .subtitle').text().trim();

    // Extract ID from URL pattern /sportstaette/-/id/XXXXX
    const idMatch = href.match(/\/id\/([^/]+)/);
    if (!idMatch || !name) return;

    venues.push({
      id: idMatch[1],
      name,
      location,
      url: href.startsWith('http') ? href : `${FUSSBALL_DE_BASE}${href}`,
    });
  });

  cache.set(cacheKey, venues);
  return venues;
}

// --- API Routes ---

/**
 * GET /api/games?venueId=XXXXX[&venueId=YYYYY]
 * Returns games for one or more venues
 */
app.get('/api/games', async (req, res) => {
  let venueIds = req.query.venueId;
  if (!venueIds) {
    return res.status(400).json({ error: 'venueId parameter required' });
  }
  if (!Array.isArray(venueIds)) {
    venueIds = [venueIds];
  }
  // Validate venue IDs: only allow alphanumeric, dashes and underscores
  const validId = /^[A-Za-z0-9_-]+$/;
  const invalidIds = venueIds.filter((id) => !validId.test(id));
  if (invalidIds.length > 0) {
    return res.status(400).json({ error: 'Invalid venue ID format' });
  }

  try {
    const results = await Promise.all(
      venueIds.map((id) => scrapeVenueGames(id))
    );
    const allGames = results.flat();
    res.json(allGames);
  } catch (err) {
    console.error('Error scraping games:', err.message);
    res.status(502).json({ error: 'Fehler beim Abrufen der Spieldaten' });
  }
});

/**
 * GET /api/search?q=Sportplatzname
 * Searches fussball.de for venues matching the query
 */
app.get('/api/search', async (req, res) => {
  const query = req.query.q;
  if (!query || query.trim().length < 2) {
    return res.status(400).json({ error: 'Suchbegriff zu kurz (min. 2 Zeichen)' });
  }

  try {
    const venues = await searchVenues(query.trim());
    res.json(venues);
  } catch (err) {
    console.error('Error searching venues:', err.message);
    res.status(502).json({ error: 'Fehler bei der Suche' });
  }
});

/**
 * GET /api/demo
 * Returns demo data for testing the UI
 */
app.get('/api/demo', (_req, res) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const makeDate = (daysOffset, hour, minute) => {
    const d = new Date(today);
    d.setDate(d.getDate() + daysOffset);
    d.setHours(hour, minute, 0, 0);
    return d;
  };

  const fmt = (d) =>
    `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
  const fmtTime = (d) =>
    `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

  const games = [
    { daysOffset: 0, hour: 10, minute: 0, home: 'SV Demo 1', guest: 'FC Test A', competition: 'Kreisliga', venueId: 'platz1', venueName: 'Sportplatz 1' },
    { daysOffset: 0, hour: 12, minute: 0, home: 'VfB Demo 2', guest: 'TSV Test B', competition: 'Kreispokal', venueId: 'platz1', venueName: 'Sportplatz 1' },
    { daysOffset: 1, hour: 15, minute: 0, home: 'SC Demo 3', guest: 'FC Test C', competition: 'A-Junioren', venueId: 'platz1', venueName: 'Sportplatz 1' },
    { daysOffset: 2, hour: 11, minute: 0, home: 'FC Demo 4', guest: 'SV Test D', competition: 'Kreisliga', venueId: 'platz2', venueName: 'Sportplatz 2' },
    { daysOffset: 2, hour: 14, minute: 0, home: 'TSV Demo 5', guest: 'VfL Test E', competition: 'B-Junioren', venueId: 'platz2', venueName: 'Sportplatz 2' },
    { daysOffset: 3, hour: 9, minute: 30, home: 'SV Demo 6', guest: 'SC Test F', competition: 'C-Junioren', venueId: 'platz1', venueName: 'Sportplatz 1' },
    { daysOffset: 4, hour: 16, minute: 0, home: 'FC Demo 7', guest: 'TSV Test G', competition: 'Kreisliga', venueId: 'platz1', venueName: 'Sportplatz 1' },
    { daysOffset: 5, hour: 11, minute: 0, home: 'VfB Demo 8', guest: 'SV Test H', competition: 'Kreispokal', venueId: 'platz2', venueName: 'Sportplatz 2' },
    { daysOffset: 6, hour: 13, minute: 0, home: 'SC Demo 9', guest: 'FC Test I', competition: 'A-Junioren', venueId: 'platz2', venueName: 'Sportplatz 2' },
  ].map((g) => {
    const d = makeDate(g.daysOffset, g.hour, g.minute);
    return {
      venueId: g.venueId,
      venueName: g.venueName,
      date: fmt(d),
      time: fmtTime(d),
      homeTeam: g.home,
      guestTeam: g.guest,
      competition: g.competition,
      startDate: d.toISOString(),
    };
  });

  res.json(games);
});

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => {
  console.log(`Platzbelegung server running on http://localhost:${PORT}`);
});

module.exports = { app, server };
