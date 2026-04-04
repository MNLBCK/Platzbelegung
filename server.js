'use strict';

const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const NodeCache = require('node-cache');
const path = require('path');
const fs = require('fs');
const yaml = require('js-yaml');

const app = express();
const cache = new NodeCache({ stdTTL: 300 }); // 5 min cache

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const FUSSBALL_DE_BASE = 'https://www.fussball.de';
const DATA_DIR = path.join(__dirname, 'data');
const LATEST_SNAPSHOT = path.join(DATA_DIR, 'latest.json');
const CONFIG_FILE = path.join(__dirname, 'config.yaml');

const HTTP_HEADERS = {
  'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'de-DE,de;q=0.9,en;q=0.5',
  'Accept-Encoding': 'gzip, deflate, br',
  Connection: 'keep-alive',
};

function normalizeText(value) {
  return String(value || '')
    .replace(/\u200b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function toAbsoluteUrl(url) {
  if (!url) return '';
  if (url.startsWith('http')) return url;
  if (url.startsWith('//')) return `https:${url}`;
  if (url.startsWith('/')) return `${FUSSBALL_DE_BASE}${url}`;
  return url;
}

function slugifyVenue(value) {
  const base = normalizeText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return base || 'unbekannte-spielstaette';
}

/**
 * Load and parse the config.yaml file.
 * Returns parsed config object, or null on error.
 * @returns {object|null}
 */
function loadConfig() {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, 'utf8');
    return yaml.load(raw) || {};
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.error('Error reading config.yaml:', err.message);
    }
    return null;
  }
}

/**
 * Write config object back to config.yaml, preserving formatting as much as possible.
 * Returns true on success, false on error.
 * @param {object} config
 * @returns {boolean}
 */
function saveConfig(config) {
  try {
    const raw = yaml.dump(config, {
      indent: 2,
      lineWidth: 120,
      noRefs: true,
      quotingType: '"',
    });
    fs.writeFileSync(CONFIG_FILE, raw, 'utf8');
    return true;
  } catch (err) {
    console.error('Error writing config.yaml:', err.message);
    return false;
  }
}


function loadLatestSnapshot() {
  try {
    const raw = fs.readFileSync(LATEST_SNAPSHOT, 'utf8');
    return JSON.parse(raw);
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.error('Error reading snapshot:', err.message);
    }
    return null;
  }
}

/**
 * Parse a German date/time string from fussball.de
 * Typical formats: "28.03.2026 14:00" or "28.03.2026"
 * @param {string} dateStr
 * @param {string} timeStr
 * @returns {Date|null}
 */
function parseGermanDate(dateStr, timeStr) {
  if (!dateStr) return null;
  let match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{4})/);
  let day;
  let month;
  let year;
  if (match) {
    [, day, month, year] = match;
  } else {
    match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{2})/);
    if (!match) return null;
    [, day, month, year] = match;
    year = `20${year}`;
  }
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

function formatGermanDate(date) {
  return [
    String(date.getDate()).padStart(2, '0'),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getFullYear()),
  ].join('.');
}

/**
 * Search fussball.de for clubs (Vereine) by name.
 * @param {string} query - search term
 * @returns {Promise<Array>} Array of club objects {id, name, location, url}
 */
async function searchClubs(query) {
  const cacheKey = `clubs_${query}`;
  const cached = cache.get(cacheKey);
  if (cached) return cached;

  const url = `${FUSSBALL_DE_BASE}/suche/-/text/${encodeURIComponent(query)}/restriction/CLUB_AND_TEAM#!/`;

  const response = await axios.get(url, {
    headers: HTTP_HEADERS,
    timeout: 15000,
    maxContentLength: 5 * 1024 * 1024,
  });

  const $ = cheerio.load(response.data);
  const clubs = [];

  $('#club-search-results #clublist li').each((_, item) => {
    const link = $(item).find('a.image-wrapper').first();
    const href = link.attr('href') || '';
    const name = normalizeText(link.find('.name').first().text());
    const location = normalizeText(link.find('.sub').first().text());
    const logoUrl = toAbsoluteUrl(link.find('img').first().attr('src') || '');

    const idMatch = href.match(/\/id\/([^/?#]+)/);
    if (!idMatch || !name) return;

    clubs.push({
      id: idMatch[1],
      name,
      location,
      logoUrl,
      url: href.startsWith('http') ? href : `${FUSSBALL_DE_BASE}${href}`,
    });
  });

  cache.set(cacheKey, clubs);
  return clubs;
}

function parseClubMatchplanHtml(html) {
  const $ = cheerio.load(html);
  const games = [];

  let currentDate = '';
  let currentTime = '';
  let currentCompetition = '';

  $('table.table-striped tbody tr').each((_, row) => {
    const $row = $(row);
    const classes = ($row.attr('class') || '').split(/\s+/).filter(Boolean);

    if (classes.includes('row-headline') || classes.includes('row-venue')) {
      return;
    }

    if (classes.includes('row-competition')) {
      const dateText = normalizeText($row.find('.column-date').first().text());
      const competitionText = normalizeText($row.find('.column-team').first().text());
      const dateMatch = dateText.match(/(\d{2}\.\d{2}\.(?:\d{2}|\d{4}))/);
      const timeMatch = dateText.match(/(\d{2}:\d{2})/);
      currentDate = dateMatch ? dateMatch[1] : '';
      currentTime = timeMatch ? timeMatch[1] : '';
      currentCompetition = competitionText;
      return;
    }

    const clubCells = $row.find('td.column-club');
    const homeTeam = normalizeText($(clubCells[0]).find('.club-name').text() || $(clubCells[0]).text());
    const guestTeam = normalizeText($(clubCells[1]).find('.club-name, .info-text').text() || $(clubCells[1]).text());
    if (!currentDate || !homeTeam) return;
    if (/^(spielfrei|bye)$/i.test(homeTeam) || /^(spielfrei|bye)$/i.test(guestTeam)) return;

    // Extract club logo URLs: try direct img src first, then href-based club ID
    function extractLogoUrl(cell) {
      const imgSrc = $(cell).find('img').first().attr('src');
      if (imgSrc) return toAbsoluteUrl(imgSrc);
      const href = $(cell).find('.club-wrapper, a').first().attr('href') || '';
      const idMatch = href.match(/\/id\/([^/?#]+)/);
      if (idMatch) {
        return `https://www.fussball.de/export.media/-/action/getLogo/format/7/id/${idMatch[1]}`;
      }
      return '';
    }
    const homeLogoUrl  = extractLogoUrl(clubCells[0]);
    const guestLogoUrl = extractLogoUrl(clubCells[1]);

    const $venueRow = $row.nextAll('tr.row-venue').first();
    let venueName = '';
    if ($venueRow.length > 0) {
      let blockedByNextCompetition = false;
      $row.nextAll('tr').each((__, nextRow) => {
        if (nextRow === $venueRow[0]) return false;
        const nextClasses = (nextRow.attribs.class || '').split(/\s+/).filter(Boolean);
        if (nextClasses.includes('row-competition')) {
          blockedByNextCompetition = true;
          return false;
        }
        return undefined;
      });
      if (!blockedByNextCompetition) {
        venueName = normalizeText($venueRow.find('td[colspan="3"]').first().text() || $venueRow.text());
      }
    }

    const parsedDate = parseGermanDate(currentDate, currentTime);
    if (!parsedDate) return;

    games.push({
      venueId: slugifyVenue(venueName),
      venueName,
      date: formatGermanDate(parsedDate),
      time: currentTime,
      homeTeam,
      homeLogoUrl,
      guestTeam,
      guestLogoUrl,
      competition: currentCompetition,
      startDate: parsedDate.toISOString(),
    });
  });

  return games;
}

async function fetchClubMatchplan(clubId, dateFrom, dateTo, matchType = 1, max = 100, offset = 0) {
  const cacheKey = `matchplan_${clubId}_${dateFrom}_${dateTo}_${matchType}_${max}_${offset}`;
  const cached = cache.get(cacheKey);
  if (cached) return cached;

  const url = `${FUSSBALL_DE_BASE}/ajax.club.matchplan/-/id/${encodeURIComponent(clubId)}/mode/PAGE/show-filter/false/max/${encodeURIComponent(String(max))}/datum-von/${encodeURIComponent(dateFrom)}/datum-bis/${encodeURIComponent(dateTo)}/match-type/${encodeURIComponent(String(matchType))}/show-venues/checked/offset/${encodeURIComponent(String(offset))}`;
  const response = await axios.get(url, {
    headers: HTTP_HEADERS,
    timeout: 15000,
    maxContentLength: 5 * 1024 * 1024,
  });
  const games = parseClubMatchplanHtml(response.data);
  cache.set(cacheKey, games);
  return games;
}

/**
 * Search fussball.de for venues by name (used by the venue discovery UI).
 * This search is lightweight and does not duplicate the Python scraper's
 * data-collection role.
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
    maxContentLength: 5 * 1024 * 1024,
  });

  const $ = cheerio.load(response.data);
  const venues = [];

  $('.search-result-item, .result-item').each((_, item) => {
    const link = $(item).find('a').first();
    const href = link.attr('href') || '';
    const name = link.text().trim() || $(item).find('.title').text().trim();
    const location = $(item).find('.location, .subtitle').text().trim();

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
 * GET /api/snapshot
 * Returns the full latest JSON snapshot (written by the Python scraper).
 * Includes metadata (generated_at, config) and the games array.
 */
app.get('/api/snapshot', (_req, res) => {
  const snapshot = loadLatestSnapshot();
  if (!snapshot) {
    return res.status(404).json({
      error: 'Kein Snapshot vorhanden. Bitte zuerst "platzbelegung scrape" ausführen.',
    });
  }
  res.json(snapshot);
});

/**
 * GET /api/games?venueId=XXXXX[&venueId=YYYYY]
 * Returns games for one or more venues from the latest snapshot.
 * Requires at least one venueId parameter.
 */
app.get('/api/games', (req, res) => {
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

  const snapshot = loadLatestSnapshot();
  if (!snapshot) {
    return res.status(404).json({
      error: 'Kein Snapshot vorhanden. Bitte zuerst "platzbelegung scrape" ausführen.',
    });
  }

  const allGames = snapshot.games || [];
  const filtered = allGames.filter((g) => venueIds.includes(g.venueId));
  res.json(filtered);
});

/**
 * GET /api/search?q=Sportplatzname
 * Searches fussball.de for venues matching the query.
 * Used by the UI for venue discovery / adding new venues.
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
 * GET /api/search/clubs?q=Vereinsname
 * Searches fussball.de for clubs (Vereine) matching the query.
 * Used by the UI for club discovery and configuration.
 */
app.get('/api/search/clubs', async (req, res) => {
  const query = req.query.q;
  if (!query || query.trim().length < 2) {
    return res.status(400).json({ error: 'Suchbegriff zu kurz (min. 2 Zeichen)' });
  }

  try {
    const clubs = await searchClubs(query.trim());
    res.json(clubs);
  } catch (err) {
    console.error('Error searching clubs:', err.message);
    res.status(502).json({ error: 'Fehler bei der Suche' });
  }
});

/**
 * GET /api/club-matchplan?id=CLUB_ID&dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD[&matchType=1][&max=100]
 * Loads the current club matchplan directly from fussball.de and returns games
 * with extracted venues from the rendered HTML.
 */
app.get('/api/club-matchplan', async (req, res) => {
  const { id, dateFrom, dateTo } = req.query;
  const matchType = Number.parseInt(req.query.matchType, 10);
  const max = Number.parseInt(req.query.max, 10) || 100;

  if (!id || typeof id !== 'string' || !id.trim()) {
    return res.status(400).json({ error: 'Vereins-ID erforderlich.' });
  }
  if (!dateFrom || !/^\d{4}-\d{2}-\d{2}$/.test(dateFrom)) {
    return res.status(400).json({ error: 'dateFrom muss im Format YYYY-MM-DD angegeben werden.' });
  }
  if (!dateTo || !/^\d{4}-\d{2}-\d{2}$/.test(dateTo)) {
    return res.status(400).json({ error: 'dateTo muss im Format YYYY-MM-DD angegeben werden.' });
  }

  try {
    const games = await fetchClubMatchplan(
      id.trim(),
      dateFrom,
      dateTo,
      Number.isNaN(matchType) ? 1 : matchType,
      Math.min(Math.max(max, 1), 200),
      0
    );
    res.json(games);
  } catch (err) {
    console.error('Error loading club matchplan:', err.message);
    res.status(502).json({ error: 'Fehler beim Laden des Vereinsspielplans' });
  }
});

/**
 * PUT /api/config/club
 * Updates the club (Verein) configuration in config.yaml.
 * Body: { id: "CLUB_ID", name: "Club Name" }
 */
app.put('/api/config/club', (req, res) => {
  const { id, name } = req.body;
  if (!id || typeof id !== 'string' || !id.trim()) {
    return res.status(400).json({ error: 'Vereins-ID erforderlich.' });
  }

  const config = loadConfig() || {};
  config.club = { id: String(id).trim() };
  if (name && typeof name === 'string' && name.trim()) {
    config.club.name = String(name).trim();
  }

  if (!saveConfig(config)) {
    return res.status(500).json({ error: 'Konfiguration konnte nicht gespeichert werden.' });
  }

  res.json({ ok: true, club: config.club });
});

/**
 * GET /api/demo
 * Returns demo data for testing the UI without a snapshot.
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

/**
 * GET /api/config
 * Returns the current venue configuration from config.yaml.
 */
app.get('/api/config', (_req, res) => {
  const config = loadConfig();
  if (!config) {
    return res.status(404).json({ error: 'config.yaml nicht gefunden.' });
  }
  // Only expose the venues section and basic club/season info
  res.json({
    club: config.club || {},
    season: config.season || '',
    venues: config.venues || [],
  });
});

/**
 * PUT /api/config/venues
 * Replaces the venues array in config.yaml with the provided list.
 * Body: { venues: [{ id, name, aliases, name_patterns }] }
 */
app.put('/api/config/venues', (req, res) => {
  const { venues } = req.body;
  if (!Array.isArray(venues)) {
    return res.status(400).json({ error: 'venues muss ein Array sein.' });
  }

  // Validate each venue entry
  for (const v of venues) {
    if (typeof v !== 'object' || v === null) {
      return res.status(400).json({ error: 'Ungültiges Venue-Objekt.' });
    }
    if (v.aliases && !Array.isArray(v.aliases)) {
      return res.status(400).json({ error: 'aliases muss ein Array sein.' });
    }
    if (v.name_patterns && !Array.isArray(v.name_patterns)) {
      return res.status(400).json({ error: 'name_patterns muss ein Array sein.' });
    }
  }

  const config = loadConfig() || {};

  // Build cleaned venue list (keep only known fields)
  config.venues = venues.map((v) => {
    const entry = {};
    if (v.id) entry.id = String(v.id);
    if (v.name) entry.name = String(v.name);
    if (Array.isArray(v.aliases) && v.aliases.length > 0) {
      entry.aliases = v.aliases.map(String);
    }
    if (Array.isArray(v.name_patterns) && v.name_patterns.length > 0) {
      entry.name_patterns = v.name_patterns.map(String);
    }
    return entry;
  });

  if (!saveConfig(config)) {
    return res.status(500).json({ error: 'Konfiguration konnte nicht gespeichert werden.' });
  }

  res.json({ ok: true, venues: config.venues });
});

const PORT = process.env.PORT || 3210;
const server = app.listen(PORT, () => {
  console.log(`Platzbelegung server running on http://localhost:${PORT}`);
});

module.exports = {
  app,
  server,
  parseClubMatchplanHtml,
  searchClubs,
  fetchClubMatchplan,
  parseGermanDate,
  formatGermanDate,
};
