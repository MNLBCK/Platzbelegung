// ===================== Cookie Utilities =====================

function setCookie(name, value, days) {
  const d = days === undefined ? 365 : days;
  const expires = new Date(Date.now() + d * 864e5).toUTCString();
  document.cookie =
    encodeURIComponent(name) + '=' + encodeURIComponent(JSON.stringify(value)) +
    '; expires=' + expires + '; path=/; SameSite=Strict';
}

function getCookie(name) {
  const re = new RegExp('(?:^|; )' + encodeURIComponent(name) + '=([^;]*)');
  const m = document.cookie.match(re);
  if (!m) return null;
  try { return JSON.parse(decodeURIComponent(m[1])); } catch (_) { return null; }
}

function deleteCookie(name) {
  document.cookie = encodeURIComponent(name) + '=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';
}

// ===================== Session Storage (game data only) =====================

const SESSION_KEY = 'pb_session_v1';

function saveSession() {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      clubId: state.club ? state.club.id : null,
      additionalClubIds: state.additionalClubs.map(c => c.id),
      games: state.games,
      loadedFrom: state.loadedFrom,
      loadedTo: state.loadedTo,
    }));
  } catch (_) {}
}

function loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) { return null; }
}

// ===================== Constants =====================

const COOKIE_CLUB         = 'pb_club';
const COOKIE_RECENT       = 'pb_recent';
const COOKIE_VENUES       = 'pb_venues';
const COOKIE_VIEW         = 'pb_view';
const COOKIE_EXTRA_CLUBS  = 'pb_extra_clubs';

const VENUE_COLORS = [
  '#1565c0', '#6a1b9a', '#e65100', '#00695c',
  '#283593', '#558b2f', '#c62828', '#4527a0',
  '#0277bd', '#2e7d32',
];

// Colors per youth/team category (German football classification)
const TEAM_CATEGORY_COLORS = {
  'A-Junioren': '#c62828',
  'B-Junioren': '#e65100',
  'C-Junioren': '#f9a825',
  'D-Junioren': '#558b2f',
  'E-Junioren': '#00695c',
  'F-Junioren': '#0277bd',
  'G-Junioren': '#6a1b9a',
  'Bambini':    '#4527a0',
  'Herren':     '#1565c0',
  'Damen':      '#c2185b',
  'Senioren':   '#455a64',
  'Sonstige':   '#607d8b',
};

const DE_DAYS       = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
const DE_DAYS_LONG  = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
const DE_MONTHS     = ['Jan', 'Feb', 'Mar', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];
const DE_MONTHS_LONG = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];

// ===================== State =====================

const state = {
  club: null,
  additionalClubs: [],
  games: [],
  venues: [],
  venueShortNames: {},
  selectedVenueIds: null,   // null = all; array = explicit selection
  currentWeekStart: null,
  currentMonth: null,
  view: 'week',
  loadedFrom: '',
  loadedTo: '',
};

const $ = id => document.getElementById(id);

// ===================== Generic Helpers =====================

function showEl(el, show = true) {
  if (!el) return;
  el.classList.toggle('hidden', !show);
}

function showLoading(on) { showEl($('loading-indicator'), on); }

function showError(msg) {
  const el = $('error-msg');
  el.textContent = msg;
  showEl(el, !!msg);
}

function formatMetaDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function setTeamOverviewLoading() {
  const wrap = $('team-overview');
  const listEl = $('team-overview-list');
  const summaryEl = $('team-overview-summary');
  if (!wrap || !listEl || !summaryEl) return;
  wrap.open = false;
  listEl.innerHTML = '';
  summaryEl.textContent = '▸ Mannschaften werden geladen…';
  showEl(wrap, true);
}

async function loadAppMeta() {
  const badgeEl = $('app-version-badge');
  if (!badgeEl) return;

  try {
    const resp = await fetch('/api/meta');
    const data = await resp.json();
    if (!resp.ok) return;

    const version = String(data.version || '').trim();
    const releaseUrl = String(data.releaseUrl || '').trim();
    const deployedAt = formatMetaDate(data.deployedAt || '');
    const snapshotGeneratedAt = formatMetaDate(data.snapshotGeneratedAt || '');

    badgeEl.textContent = version || 'dev';
    if (releaseUrl) badgeEl.href = releaseUrl;

    const titleParts = [];
    if (deployedAt) titleParts.push('Deploy: ' + deployedAt);
    if (snapshotGeneratedAt) titleParts.push('Snapshot: ' + snapshotGeneratedAt);
    if (titleParts.length) badgeEl.title = titleParts.join(' • ');
  } catch (_) {
    badgeEl.textContent = 'dev';
  }
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function extractClubId(input) {
  const trimmed = String(input || '').trim();
  const match = trimmed.match(/\/verein\/.+?\/-\/id\/([^/?#]+)/);
  return match ? match[1] : null;
}

function formatInputDate(date) {
  return [
    String(date.getFullYear()),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
}

function getDefaultDateRange() {
  const today = new Date();
  const endOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 2, 0);
  return {
    dateFrom: formatInputDate(today),
    dateTo: formatInputDate(endOfNextMonth),
  };
}

function getMonday(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function isSameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function fmtFull(date) {
  return String(DE_DAYS_LONG[date.getDay()]) + ', ' + date.getDate() + '. ' + DE_MONTHS_LONG[date.getMonth()] + ' ' + date.getFullYear();
}

function getISOWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

function venueColor(venueId) {
  const idx = state.venues.findIndex(v => v.id === venueId);
  return VENUE_COLORS[idx % VENUE_COLORS.length] || '#607d8b';
}

function deriveShortVenueName(fullName) {
  const parts = splitVenueParts(fullName);
  const base = parts[0] || 'Unbekannt';
  return truncateShortName(base);
}

function splitVenueParts(fullName) {
  return String(fullName || '')
    .split(',')
    .map(p => p.trim())
    .filter(Boolean);
}

function truncateShortName(value, maxLen = 32) {
  const text = String(value || '').trim();
  if (!text) return 'Unbekannt';
  return text.length <= maxLen ? text : text.slice(0, maxLen - 1) + '\u2026';
}

function pickDetailPart(parts, siblingParts) {
  const rest = parts.slice(1);

  const pitch = rest.find(p => /platz\s*\d+/i.test(p) || /\bplatz\b/i.test(p));
  if (pitch) return pitch;

  const stadium = rest.find(p => /(stadion|arena)/i.test(p));
  if (stadium) return stadium;

  for (let i = 1; i < parts.length; i++) {
    const candidate = parts[i];
    if (!candidate) continue;
    if (siblingParts.some(sp => (sp[i] || '') !== candidate)) return candidate;
  }

  return rest.find(Boolean) || '';
}

function computeVenueShortNames(venues) {
  const parsed = venues.map(v => {
    const name = v.name || 'Unbekannte Spielstätte';
    const parts = splitVenueParts(name);
    return { id: v.id, name, parts };
  });

  const baseCounts = new Map();
  parsed.forEach(p => {
    const base = p.parts[0] || 'Unbekannt';
    const key = base.toLowerCase();
    baseCounts.set(key, (baseCounts.get(key) || 0) + 1);
  });

  const usedShort = new Set();
  const result = new Map();

  parsed.forEach(p => {
    const base = p.parts[0] || 'Unbekannt';
    const key = base.toLowerCase();
    const needsDetail = (baseCounts.get(key) || 0) > 1;

    let shortName = base;
    if (needsDetail) {
      const siblings = parsed
        .filter(sp => (sp.parts[0] || 'Unbekannt') === base)
        .map(sp => sp.parts);
      const detail = pickDetailPart(p.parts, siblings);
      if (detail) shortName = base + ' – ' + detail;
    }

    shortName = truncateShortName(shortName);

    if (usedShort.has(shortName)) {
      const altDetail = p.parts.slice(1).join(', ') || p.name;
      shortName = truncateShortName(base + ' – ' + altDetail);
    }

    let suffix = 2;
    while (usedShort.has(shortName)) {
      shortName = truncateShortName(base + ' #' + suffix);
      suffix += 1;
    }

    usedShort.add(shortName);
    result.set(p.id, shortName);
  });

  return result;
}

function updateVenueShortNames() {
  const map = computeVenueShortNames(state.venues || []);
  state.venueShortNames = Object.fromEntries(map.entries());
}

function getVenueShortNameForGame(game) {
  const vid = deriveVenueId(game);
  if (state.venueShortNames && state.venueShortNames[vid]) {
    return state.venueShortNames[vid];
  }
  return deriveShortVenueName(game.venueName || '');
}

function deriveVenueId(game) {
  return game.venueId || game.venueName || 'unbekannte-spielstaette';
}

function deriveVenuesFromGames(games) {
  const seen = new Set();
  return games.reduce((acc, game) => {
    const id = deriveVenueId(game);
    const name = game.venueName || 'Unbekannte Spielstätte';
    if (seen.has(id)) return acc;
    seen.add(id);
    acc.push({ id, name });
    return acc;
  }, []);
}

function isVenueSelected(venueId) {
  if (!state.selectedVenueIds) return true;
  return state.selectedVenueIds.includes(venueId);
}

function getVisibleVenues() {
  return state.venues.filter(v => isVenueSelected(v.id));
}

// ===================== Team Category Helpers =====================

function deriveTeamCategory(game) {
  const text = ((game.competition || '') + ' ' + (game.homeTeam || '') + ' ' + (game.guestTeam || '')).toLowerCase();
  if (/\bbambini\b/.test(text)) return 'Bambini';
  if (/\bdamen\b|\bfrauen\b/.test(text)) return 'Damen';
  const juniorinnen = text.match(/\b([a-g])[-\s]junior(?:en|innen)\b/i);
  if (juniorinnen) return juniorinnen[1].toUpperCase() + '-Junioren';
  const u = text.match(/\bu\s*(\d+)\b/i);
  if (u) {
    const age = parseInt(u[1], 10);
    if (age <= 7)  return 'G-Junioren';
    if (age <= 9)  return 'F-Junioren';
    if (age <= 11) return 'E-Junioren';
    if (age <= 13) return 'D-Junioren';
    if (age <= 15) return 'C-Junioren';
    if (age <= 17) return 'B-Junioren';
    if (age <= 19) return 'A-Junioren';
  }
  if (/\bherren\b/.test(text))   return 'Herren';
  if (/\bsenioren\b/.test(text)) return 'Senioren';
  return 'Sonstige';
}

function teamCategoryColor(game) {
  const cat = deriveTeamCategory(game);
  return TEAM_CATEGORY_COLORS[cat] || TEAM_CATEGORY_COLORS['Sonstige'];
}

// Returns the opponent's name: tries to detect which team belongs to our clubs
function getOpponent(game) {
  const allClubs = getAllClubs();
  if (!allClubs.length) return game.guestTeam || '';
  const htLow = (game.homeTeam  || '').toLowerCase();
  const gtLow = (game.guestTeam || '').toLowerCase();
  for (const club of allClubs) {
    const clubName = (club.name || '').toLowerCase();
    if (!clubName) continue;
    if (clubName.length >= 4) {
      if (htLow.includes(clubName)) return game.guestTeam || '';
      if (gtLow.includes(clubName)) return game.homeTeam  || '';
    }
    const key = clubName.split(/\s+/).find(w => w.length > 2);
    if (key) {
      const wordRe = new RegExp('(?:^|\\s)' + key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:\\s|$)');
      if (wordRe.test(htLow)) return game.guestTeam || '';
      if (wordRe.test(gtLow)) return game.homeTeam  || '';
    }
  }
  return game.guestTeam || '';
}

// Returns the logo URL for the opponent team
function getOpponentLogoUrl(game) {
  const allClubs = getAllClubs();
  if (!allClubs.length) return game.guestLogoUrl || '';
  const htLow = (game.homeTeam  || '').toLowerCase();
  const gtLow = (game.guestTeam || '').toLowerCase();
  for (const club of allClubs) {
    const clubName = (club.name || '').toLowerCase();
    if (!clubName) continue;
    if (clubName.length >= 4) {
      if (htLow.includes(clubName)) return game.guestLogoUrl || '';
      if (gtLow.includes(clubName)) return game.homeLogoUrl  || '';
    }
    const key = clubName.split(/\s+/).find(w => w.length > 2);
    if (key) {
      const wordRe = new RegExp('(?:^|\\s)' + key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:\\s|$)');
      if (wordRe.test(htLow)) return game.guestLogoUrl || '';
      if (wordRe.test(gtLow)) return game.homeLogoUrl  || '';
    }
  }
  return game.guestLogoUrl || '';
}

function getClubUrl(club) {
  if (!club || !club.id) return '';
  if (club.url) return club.url;
  return 'https://www.fussball.de/verein/-/id/' + encodeURIComponent(club.id) + '#!/';
}

function getGameResult(game) {
  const result = String(game.result || '').trim();
  if (!result || result === '-:-') return '';
  const start = new Date(game.startDate || '');
  if (isNaN(start.getTime()) || start > new Date()) return '';
  return result;
}

function getTeamSortRank(entry) {
  const text = ((entry.competition || '') + ' ' + (entry.team || '')).toLowerCase();
  if (/\bherren\b/.test(text)) return 0;
  if (/\bdamen\b/.test(text)) return 1;
  if (/\ba-junior/.test(text) || /\bu19\b/.test(text)) return 2;
  if (/\bb-junior/.test(text) || /\bu17\b/.test(text)) return 3;
  if (/\bc-junior/.test(text) || /\bu15\b/.test(text)) return 4;
  if (/\bd-junior/.test(text) || /\bu13\b/.test(text)) return 5;
  if (/\be-junior/.test(text) || /\bu11\b/.test(text)) return 6;
  if (/\bf-junior/.test(text) || /\bu9\b/.test(text)) return 7;
  if (/\bg-junior/.test(text) || /\bbambini\b|\bu7\b/.test(text)) return 8;
  return 9;
}

function getTeamEntries() {
  const seen = new Map();
  const entries = [];
  state.games.forEach(game => {
    const team = game.homeTeam || game.guestTeam || '';
    const competition = game.competition || '';
    const key = (team + '|' + competition).toLowerCase();
    if (!team || seen.has(key)) return;
    seen.set(key, true);
    entries.push({ team, competition });
  });
  entries.sort((a, b) => {
    const rankDiff = getTeamSortRank(a) - getTeamSortRank(b);
    if (rankDiff !== 0) return rankDiff;
    return a.team.localeCompare(b.team, 'de');
  });
  return entries;
}

function renderTeamOverview() {
  const wrap = $('team-overview');
  const listEl = $('team-overview-list');
  const summaryEl = $('team-overview-summary');
  if (!wrap || !listEl || !summaryEl) return;
  if (!state.club || !state.club.id || !state.games.length) {
    wrap.open = false;
    showEl(wrap, false);
    listEl.innerHTML = '';
    summaryEl.textContent = '▸ Mannschaften';
    return;
  }
  const teams = getTeamEntries();
  const isOpen = wrap.hasAttribute('open');
  summaryEl.textContent = (isOpen ? '▾ ' : '▸ ') + teams.length + ' Mannschaften';
  listEl.innerHTML =
    '<div class="team-overview-table team-overview-table--head">' +
      '<span>Team</span>' +
      '<span>Spielklasse</span>' +
    '</div>' +
    teams.map(entry =>
      '<div class="team-overview-table">' +
        '<span class="team-overview-name">' + escapeHtml(entry.team) + '</span>' +
        '<span class="team-overview-comp">' + escapeHtml(entry.competition || '–') + '</span>' +
      '</div>'
    ).join('');
  wrap.ontoggle = () => {
    summaryEl.textContent = (wrap.open ? '▾ ' : '▸ ') + teams.length + ' Mannschaften';
  };
  showEl(wrap, teams.length > 0);
}

function updateSectionVisibility() {
  const hasClub = !!(state.club && state.club.id);
  showEl($('section-spielstaetten'), hasClub);
  showEl($('section-kalender'), hasClub);
}

// ===================== Cookie Persistence =====================

function loadFromCookies() {
  state.club = getCookie(COOKIE_CLUB);
  const savedView = getCookie(COOKIE_VIEW);
  if (savedView === 'week' || savedView === 'month') state.view = savedView;
  const savedVenues = getCookie(COOKIE_VENUES);
  state.selectedVenueIds = Array.isArray(savedVenues) ? savedVenues : null;
  const savedExtra = getCookie(COOKIE_EXTRA_CLUBS);
  state.additionalClubs = Array.isArray(savedExtra) ? savedExtra : [];
}

function saveClubCookie() {
  if (state.club) {
    setCookie(COOKIE_CLUB, state.club);
  } else {
    deleteCookie(COOKIE_CLUB);
  }
}

function saveAdditionalClubsCookie() {
  if (state.additionalClubs.length > 0) {
    setCookie(COOKIE_EXTRA_CLUBS, state.additionalClubs);
  } else {
    deleteCookie(COOKIE_EXTRA_CLUBS);
  }
}

function saveViewCookie() {
  setCookie(COOKIE_VIEW, state.view);
}

function saveVenuesCookie() {
  if (state.selectedVenueIds === null) {
    deleteCookie(COOKIE_VENUES);
  } else {
    setCookie(COOKIE_VENUES, state.selectedVenueIds);
  }
}

// ===================== Recent Clubs =====================

function loadRecentClubs() {
  return getCookie(COOKIE_RECENT) || [];
}

function saveRecentClub(club) {
  if (!club || !club.id) return;
  let list = loadRecentClubs();
  list = list.filter(c => c.id !== club.id);
  list.unshift({
    id: club.id,
    name: club.name || club.id,
    location: club.location || '',
    logoUrl: club.logoUrl || '',
  });
  list = list.slice(0, 3);
  setCookie(COOKIE_RECENT, list);
}

function renderRecentClubs() {
  const container = $('recent-clubs');
  const list = loadRecentClubs();
  if (!list.length) { showEl(container, false); return; }
  showEl(container, true);
  container.innerHTML =
    '<div class="recent-clubs-head">' +
      '<div class="recent-clubs-label">Zuletzt verwendet:</div>' +
      '<button type="button" class="recent-clubs-reset" id="recent-clubs-reset">zurücksetzen</button>' +
    '</div>' +
    '<div class="recent-clubs-list">' +
    list.map(club =>
      '<button class="recent-club-btn" type="button" data-club-id="' + escapeHtml(club.id) + '" title="' + escapeHtml(club.name) + (club.location ? ' \u00b7 ' + escapeHtml(club.location) : '') + '">' +
      '<span class="recent-club-logo-wrap">' +
      (club.logoUrl
        ? '<img class="recent-club-logo" src="' + escapeHtml(club.logoUrl) + '" alt="' + escapeHtml(club.name) + '" loading="lazy">'
        : '<span class="recent-club-logo-fallback">' + escapeHtml((club.name || '?').charAt(0).toUpperCase()) + '</span>') +
      '</span>' +
      '<span class="recent-club-name">' + escapeHtml(club.name) + '</span>' +
      '</button>'
    ).join('') +
    '</div>';
  const resetBtn = $('recent-clubs-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      deleteCookie(COOKIE_RECENT);
      clearClub();
      renderRecentClubs();
    });
  }
  container.querySelectorAll('[data-club-id]').forEach(button => {
    button.addEventListener('click', () => {
      const club = list.find(c => c.id === button.dataset.clubId);
      if (club) selectClub(club);
    });
  });
}

// ===================== Club Selection =====================

function selectClub(club) {
  state.club = club;
  state.additionalClubs = [];
  state.games = [];
  state.venues = [];
  state.venueShortNames = {};
  state.loadedFrom = '';
  state.loadedTo = '';
  state.selectedVenueIds = null;
  saveClubCookie();
  saveAdditionalClubsCookie();
  saveRecentClub(club);
  saveVenuesCookie();
  renderSelectedClub();
  renderRecentClubs();
  updateSectionVisibility();
  renderVenueCheckboxes();
  setTeamOverviewLoading();
  hideSGSuggestion();
  $('club-search-input').value = '';
  const resultsEl = $('club-search-results');
  resultsEl.innerHTML = '';
  showEl(resultsEl, false);
  autoLoadGames();
}

function renderSelectedClub() {
  const el = $('selected-club-info');
  if (!el) return;
  const club = state.club;
  if (!club) {
    el.innerHTML =
      '<div class="selected-club-label">Ausgewählter Verein</div>' +
      '<div class="selected-club-card selected-club-card--empty">Bitte Verein auswählen</div>';
    showEl(el, true);
    return;
  }
  const allClubs = getAllClubs();
  const label = allClubs.length > 1 ? 'Ausgewählte Vereine' : 'Ausgewählter Verein';
  const cardsHtml = allClubs.map((c, i) => {
    const isPrimary = i === 0;
    const logoHtml = c.logoUrl
      ? '<img class="selected-club-logo" src="' + escapeHtml(c.logoUrl) + '" alt="' + escapeHtml(c.name) + '" loading="lazy">'
      : '<span class="selected-club-logo-fallback">' + escapeHtml((c.name || '?').charAt(0).toUpperCase()) + '</span>';
    const clubUrl = getClubUrl(c);
    const removeBtn = !isPrimary
      ? '<button class="sg-remove-club-btn" data-club-id="' + escapeHtml(c.id) + '" title="Verein entfernen" aria-label="Verein entfernen">\u00d7</button>'
      : '';
    return (
      '<div class="selected-club-card' + (!isPrimary ? ' selected-club-card--additional' : '') + '">' +
        '<div class="selected-club-logo-wrap">' + logoHtml + '</div>' +
        '<div class="selected-club-details">' +
          '<div class="selected-club-name">' + escapeHtml(c.name) + '</div>' +
          (c.location ? '<div class="selected-club-location">' + escapeHtml(c.location) + '</div>' : '') +
          (clubUrl ? '<div class="selected-club-link"><a href="' + escapeHtml(clubUrl) + '" target="_blank" rel="noopener noreferrer">Verein auf fussball.de &#8599;</a></div>' : '') +
        '</div>' +
        removeBtn +
      '</div>'
    );
  }).join('');
  el.innerHTML = '<div class="selected-club-label">' + label + '</div>' + cardsHtml;
  el.querySelectorAll('.sg-remove-club-btn').forEach(btn => {
    btn.addEventListener('click', () => removeAdditionalClub(btn.dataset.clubId));
  });
  showEl(el, true);
}

function clearClub() {
  state.club = null;
  state.additionalClubs = [];
  state.games = [];
  state.venues = [];
  state.venueShortNames = {};
  state.selectedVenueIds = null;
  state.loadedFrom = '';
  state.loadedTo = '';
  saveClubCookie();
  saveAdditionalClubsCookie();
  saveVenuesCookie();
  sessionStorage.removeItem(SESSION_KEY);
  renderSelectedClub();
  renderVenueCheckboxes();
  updateSectionVisibility();
  hideSGSuggestion();
  $('club-search-input').value = '';
  showEl($('week-view'), false);
  showEl($('month-view'), false);
  showEl($('no-games-msg'), true);
  $('current-period-label').textContent = '';
}

// ===================== Club Search =====================

function renderClubSearchResults(clubs) {
  const resultsEl = $('club-search-results');
  if (!clubs.length) {
    resultsEl.innerHTML = '<div class="search-no-results">Keine Vereine gefunden.</div>';
    showEl(resultsEl, true);
    return;
  }
  resultsEl.innerHTML = clubs.map(club =>
    '<button class="search-result-item club-search-item" type="button" data-club-id="' + escapeHtml(club.id) + '">' +
    '<span class="club-search-logo-wrap">' +
    (club.logoUrl
      ? '<img class="club-search-logo" src="' + escapeHtml(club.logoUrl) + '" alt="">'
      : '<span class="club-search-logo club-search-logo-fallback"></span>') +
    '</span>' +
    '<span class="club-search-copy">' +
    '<span class="search-result-name">' + escapeHtml(club.name) + '</span>' +
    '<span class="search-result-loc">' + escapeHtml(club.location || club.id) + '</span>' +
    '</span>' +
    '</button>'
  ).join('');
  resultsEl.querySelectorAll('[data-club-id]').forEach(button => {
    button.addEventListener('click', () => {
      const club = clubs.find(e => e.id === button.dataset.clubId);
      if (club) selectClub(club);
    });
  });
  showEl(resultsEl, true);
}

async function doClubSearch(query) {
  const directClubId = extractClubId(query);
  if (directClubId) {
    selectClub({ id: directClubId, name: query.trim() });
    return;
  }
  const resultsEl = $('club-search-results');
  resultsEl.innerHTML = '<div class="search-no-results">Suche läuft\u2026</div>';
  showEl(resultsEl, true);
  try {
    const resp = await fetch('/api/search/clubs?q=' + encodeURIComponent(query));
    const data = await resp.json();
    if (!resp.ok) {
      resultsEl.innerHTML = '<div class="search-no-results">' + escapeHtml(data.error || 'Fehler bei der Suche') + '</div>';
      return;
    }
    renderClubSearchResults(Array.isArray(data) ? data : []);
  } catch (err) {
    resultsEl.innerHTML = '<div class="search-no-results">Netzwerkfehler: ' + escapeHtml(err.message) + '</div>';
  }
}

// ===================== Game Loading =====================

function getAllClubs() {
  const clubs = [];
  if (state.club) clubs.push(state.club);
  state.additionalClubs.forEach(c => clubs.push(c));
  return clubs;
}

async function autoLoadGames() {
  if (!state.club || !state.club.id) return;

  // Restore from session if same clubs
  const session = loadSession();
  const sessionClubId = session ? session.clubId : null;
  const sessionAdditionalIds = Array.isArray(session && session.additionalClubIds) ? session.additionalClubIds : [];
  const currentAdditionalIds = state.additionalClubs.map(c => c.id);
  const sameClubs =
    session &&
    sessionClubId === state.club.id &&
    sessionAdditionalIds.length === currentAdditionalIds.length &&
    currentAdditionalIds.every(id => sessionAdditionalIds.includes(id)) &&
    Array.isArray(session.games) && session.games.length > 0;

  if (sameClubs) {
    state.games = session.games;
    state.loadedFrom = session.loadedFrom;
    state.loadedTo = session.loadedTo;
    state.venues = deriveVenuesFromGames(state.games);
    updateVenueShortNames();
    reconcileVenueSelection();
    renderVenueCheckboxes();
    renderTeamOverview();
    renderCurrentView();
    return;
  }

  const { dateFrom, dateTo } = getDefaultDateRange();
  await fetchGames(dateFrom, dateTo);
}

async function fetchGamesForClub(club, dateFrom, dateTo) {
  const clubId = club && club.id ? club.id : '';
  if (!clubId) return [];
  const url =
    '/api/club-matchplan?id=' + encodeURIComponent(clubId) +
    '&dateFrom=' + encodeURIComponent(dateFrom) +
    '&dateTo=' + encodeURIComponent(dateTo) +
    '&clubName=' + encodeURIComponent(club.name || '') +
    '&clubLogoUrl=' + encodeURIComponent(club.logoUrl || '') +
    '&clubLocation=' + encodeURIComponent(club.location || '') +
    '&matchType=1&max=100';
  try {
    const resp = await fetch(url);
    if (!resp.ok) return [];
    const data = await resp.json();
    return Array.isArray(data) ? data : [];
  } catch (_) {
    return [];
  }
}

async function fetchGames(dateFrom, dateTo) {
  const allClubs = getAllClubs();
  if (!allClubs.length) return;
  showEl($('venues-loading'), true);
  showEl($('venues-empty'), false);
  showEl($('venues-error'), false);
  showError('');
    showLoading(true);
  try {
    const results = await Promise.all(
      allClubs.map(club => fetchGamesForClub(club, dateFrom, dateTo))
    );
    const gameKey = g => `${g.startDate}|${g.venueId || ''}|${g.homeTeam || ''}|${g.guestTeam || ''}`;
    const seen = new Set();
    const merged = [];
    results.flat().forEach(g => {
      const key = gameKey(g);
      if (!seen.has(key)) { seen.add(key); merged.push(g); }
    });
    merged.sort((a, b) => new Date(a.startDate) - new Date(b.startDate));
    state.games = merged;
    state.loadedFrom = dateFrom;
    state.loadedTo = dateTo;
    state.venues = deriveVenuesFromGames(state.games);
    updateVenueShortNames();
    reconcileVenueSelection();
    saveSession();
    renderVenueCheckboxes();
    renderTeamOverview();
    renderCurrentView();
    await detectAndSuggestSGPartners();
  } catch (err) {
    showError('Netzwerkfehler: ' + err.message);
    const errEl = $('venues-error');
    errEl.textContent = 'Fehler beim Laden der Spielstätten.';
    showEl(errEl, true);
  } finally {
    showEl($('venues-loading'), false);
    showLoading(false);
  }
}

async function extendDateRangeAndReload(newFrom, newTo) {
  const allClubs = getAllClubs();
  if (!allClubs.length) return;
  showLoading(true);
  try {
    const results = await Promise.all(
      allClubs.map(club => fetchGamesForClub(club, newFrom, newTo))
    );
    const newGames = results.flat();
    const gameKey = g => `${g.startDate}|${g.venueId || ''}|${g.homeTeam || ''}|${g.guestTeam || ''}`;
    const existingKeys = new Set(state.games.map(gameKey));
    const merged = state.games.concat(newGames.filter(g => !existingKeys.has(gameKey(g))));
    merged.sort((a, b) => new Date(a.startDate) - new Date(b.startDate));
    state.games = merged;
    state.loadedFrom = newFrom;
    state.loadedTo = newTo;
    state.venues = deriveVenuesFromGames(state.games);
    updateVenueShortNames();
    reconcileVenueSelection();
    saveSession();
    renderVenueCheckboxes();
    renderTeamOverview();
    renderCurrentView();
  } catch (_) {
    // silent fail
  } finally {
    showLoading(false);
  }
}

function checkAndExtendRange(targetDate) {
  if (!getAllClubs().length || !state.loadedFrom || !state.loadedTo) return;
  const rangeEnd =
    state.view === 'week'
      ? addDays(targetDate, 6)
      : new Date(targetDate.getFullYear(), targetDate.getMonth() + 1, 0);
  const loadedFrom = new Date(state.loadedFrom);
  const loadedTo   = new Date(state.loadedTo);
  loadedTo.setHours(23, 59, 59, 999);
  let newFrom = state.loadedFrom;
  let newTo   = state.loadedTo;
  let needsReload = false;
  if (targetDate < loadedFrom) {
    const extended = new Date(targetDate);
    extended.setMonth(extended.getMonth() - 1);
    extended.setDate(1);
    newFrom = formatInputDate(extended);
    needsReload = true;
  }
  if (rangeEnd > loadedTo) {
    const extended = new Date(rangeEnd);
    extended.setMonth(extended.getMonth() + 2);
    extended.setDate(0);
    newTo = formatInputDate(extended);
    needsReload = true;
  }
  if (needsReload) extendDateRangeAndReload(newFrom, newTo);
}

// ===================== Spielgemeinschaft Detection =====================

// Common club type prefixes to ignore when matching club keywords
const SG_CLUB_PREFIXES = new Set([
  'fc', 'sv', 'tsv', 'ssg', 'ssk', 'skv', 'vfb', 'vfr', 'tsg', 'fsv', 'bsc',
  'rfc', 'dfb', 'sg', 'sgm', 'spvg', 'sfc', 'stfc', 'asv', 'sc', 'tv', 'tb',
  'ksv', 'ssv', 'rsv', 'psv', 'gsv', 'msv', 'wsv', 'esv', 'bsv', 'hsv', 'csv',
]);

// Regex to strip German football team-type suffixes (e.g. "Herren", "A-Junioren", "U17")
const SG_TEAM_SUFFIX_RE = /\s+(?:Herren|Damen|Frauen|Senioren|(?:[A-G]-)?Junior(?:en|innen)|U\d+|Bambini|[IVX]+)\s*\d*\s*$/i;

// Minimum length for a partner name to be considered a valid club name candidate
const SG_MIN_PARTNER_LEN = 3;

function detectSpielgemeinschaftPartners(games) {
  if (!state.club || !games.length) return [];
  const clubName = (state.club.name || '').trim();
  if (!clubName) return [];

  const clubLower = clubName.toLowerCase();
  const clubKeywords = clubLower.split(/\s+/).filter(w => w.length > 3 && !SG_CLUB_PREFIXES.has(w));
  const existingIds = new Set(getAllClubs().map(c => c.id));
  const partnerNames = new Set();

  games.forEach(game => {
    [game.homeTeam, game.guestTeam].forEach(teamName => {
      if (!teamName || !teamName.includes('/')) return;

      // Strip team-type suffix, then SG/SGM prefix
      const cleaned = teamName.replace(SG_TEAM_SUFFIX_RE, '').trim().replace(/^SG[M]?\s+/i, '').trim();
      const slashIdx = cleaned.indexOf('/');
      if (slashIdx < 0) return;

      const partA = cleaned.slice(0, slashIdx).trim();
      const partB = cleaned.slice(slashIdx + 1).trim();
      if (!partA || !partB || partA.length < SG_MIN_PARTNER_LEN || partB.length < SG_MIN_PARTNER_LEN) return;

      const partALow = partA.toLowerCase();
      const partBLow = partB.toLowerCase();

      const aMatchesClub =
        partALow.includes(clubLower) ||
        clubLower.includes(partALow) ||
        (clubKeywords.length > 0 && clubKeywords.some(kw => partALow.includes(kw)));

      const bMatchesClub =
        partBLow.includes(clubLower) ||
        clubLower.includes(partBLow) ||
        (clubKeywords.length > 0 && clubKeywords.some(kw => partBLow.includes(kw)));

      if (aMatchesClub && !bMatchesClub) partnerNames.add(partB);
      else if (bMatchesClub && !aMatchesClub) partnerNames.add(partA);
    });
  });

  return Array.from(partnerNames);
}

async function detectAndSuggestSGPartners() {
  const partnerNames = detectSpielgemeinschaftPartners(state.games);
  if (!partnerNames.length) { hideSGSuggestion(); return; }

  const existingIds = new Set(getAllClubs().map(c => c.id));
  const suggestions = [];

  for (const name of partnerNames) {
    try {
      const resp = await fetch('/api/search/clubs?q=' + encodeURIComponent(name));
      if (!resp.ok) continue;
      const clubs = await resp.json();
      if (!Array.isArray(clubs)) continue;
      const match = clubs.find(c => !existingIds.has(c.id));
      if (match) {
        suggestions.push(match);
        existingIds.add(match.id); // avoid duplicates across partner names
      }
    } catch (_) {}
  }

  if (suggestions.length > 0) {
    renderSGSuggestion(suggestions);
  } else {
    hideSGSuggestion();
  }
}

function renderSGSuggestion(clubs) {
  const el = $('sg-suggestion');
  if (!el) return;
  const clubsHtml = clubs.map(club =>
    '<div class="sg-suggestion-club">' +
      (club.logoUrl ? '<img class="sg-club-logo" src="' + escapeHtml(club.logoUrl) + '" alt="" loading="lazy">' : '') +
      '<span class="sg-club-name">' + escapeHtml(club.name) + '</span>' +
      (club.location ? '<span class="sg-club-loc">' + escapeHtml(club.location) + '</span>' : '') +
      '<button class="btn btn-sm sg-add-btn" type="button" data-club-id="' + escapeHtml(club.id) + '">Hinzufügen</button>' +
    '</div>'
  ).join('');
  el.innerHTML =
    '<div class="sg-suggestion-icon">\uD83E\uDD1D</div>' +
    '<div class="sg-suggestion-body">' +
      '<div class="sg-suggestion-title">Spielgemeinschaft erkannt</div>' +
      '<div class="sg-suggestion-text">Dieser Verein spielt in einer Spielgemeinschaft. M\u00f6chten Sie die Partnervereine hinzuf\u00fcgen, um alle Spiele und Spielst\u00e4tten zu sehen?</div>' +
      '<div class="sg-suggestion-clubs">' + clubsHtml + '</div>' +
    '</div>' +
    '<button class="sg-dismiss-btn" type="button" aria-label="Schlie\u00dfen">\u00d7</button>';
  el.querySelectorAll('.sg-add-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const club = clubs.find(c => c.id === btn.dataset.clubId);
      if (club) addAdditionalClub(club);
    });
  });
  el.querySelector('.sg-dismiss-btn').addEventListener('click', hideSGSuggestion);
  showEl(el, true);
}

function hideSGSuggestion() {
  showEl($('sg-suggestion'), false);
}

async function addAdditionalClub(club) {
  if (!club || !club.id) return;
  if (state.additionalClubs.some(c => c.id === club.id)) return;
  if (state.club && state.club.id === club.id) return;
  state.additionalClubs.push({
    id: club.id,
    name: club.name || club.id,
    location: club.location || '',
    logoUrl: club.logoUrl || '',
    url: club.url || '',
  });
  saveAdditionalClubsCookie();
  renderSelectedClub();
  hideSGSuggestion();
  const dateFrom = state.loadedFrom || getDefaultDateRange().dateFrom;
  const dateTo   = state.loadedTo   || getDefaultDateRange().dateTo;
  await fetchGames(dateFrom, dateTo);
}

async function removeAdditionalClub(clubId) {
  state.additionalClubs = state.additionalClubs.filter(c => c.id !== clubId);
  saveAdditionalClubsCookie();
  renderSelectedClub();
  const dateFrom = state.loadedFrom || getDefaultDateRange().dateFrom;
  const dateTo   = state.loadedTo   || getDefaultDateRange().dateTo;
  await fetchGames(dateFrom, dateTo);
}

// ===================== Venue Selection =====================

function reconcileVenueSelection() {
  if (!state.selectedVenueIds) return;
  const validIds = new Set(state.venues.map(v => v.id));
  const filtered = state.selectedVenueIds.filter(id => validIds.has(id));
  // If no valid IDs remain or all venues are selected, null means "show all"
  state.selectedVenueIds =
    filtered.length === 0 || filtered.length === state.venues.length ? null : filtered;
  saveVenuesCookie();
}

function renderVenueCheckboxes() {
  const loadingEl = $('venues-loading');
  const emptyEl   = $('venues-empty');
  const cbEl      = $('venues-checkboxes');
  const errEl     = $('venues-error');

  showEl(loadingEl, false);
  showEl(errEl, false);

  if (!state.club || !state.club.id) {
    emptyEl.textContent = 'Bitte zuerst einen Verein auswählen.';
    showEl(emptyEl, true);
    showEl(cbEl, false);
    return;
  }

  if (!state.venues.length) {
    emptyEl.textContent = 'Keine Spielstätten gefunden.';
    showEl(emptyEl, true);
    showEl(cbEl, false);
    return;
  }

  showEl(emptyEl, false);
  showEl(cbEl, true);

  const MAPS_BASE = 'https://www.google.com/maps/search/?api=1&query=';

  cbEl.innerHTML = state.venues.map((venue, index) => {
    const color   = VENUE_COLORS[index % VENUE_COLORS.length];
    const checked = isVenueSelected(venue.id) ? 'checked' : '';
    const short   = state.venueShortNames[venue.id] || deriveShortVenueName(venue.name);
    const mapsUrl = MAPS_BASE + encodeURIComponent(venue.name);
    return (
      '<label class="venue-checkbox-item">' +
      '<input type="checkbox" data-venue-id="' + escapeHtml(venue.id) + '" ' + checked + ' />' +
      '<span class="venue-color-dot" style="background:' + color + '"></span>' +
      '<span class="venue-short-name">' + escapeHtml(short) + '</span>' +
      '<span class="venue-full-name" title="' + escapeHtml(venue.name) + '">' + escapeHtml(venue.name) + '</span>' +
      '<a class="venue-map-icon" href="' + escapeHtml(mapsUrl) + '" target="_blank" rel="noopener noreferrer" title="In Google Maps öffnen" onclick="event.stopPropagation()">&#x1F4CD;</a>' +
      '</label>'
    );
  }).join('');

  // Remove any leftover map links section
  const existingLinks = cbEl.querySelector('.venues-map-links');
  if (existingLinks) existingLinks.remove();

  cbEl.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', () => {
      const allBoxes = cbEl.querySelectorAll('input[type="checkbox"]');
      const checked  = Array.from(allBoxes).filter(b => b.checked).map(b => b.dataset.venueId);
      state.selectedVenueIds = checked.length === state.venues.length ? null : checked;
      saveVenuesCookie();
      renderCurrentView();
    });
  });
}

// ===================== Calendar Rendering =====================

function updateDatePicker() {
  const picker = $('date-picker');
  if (!picker) return;
  picker.value = state.view === 'week'
    ? formatInputDate(state.currentWeekStart)
    : formatInputDate(state.currentMonth);
}

function renderCurrentView() {
  if (!state.currentWeekStart) state.currentWeekStart = getMonday(new Date());
  if (!state.currentMonth) {
    const t = new Date();
    state.currentMonth = new Date(t.getFullYear(), t.getMonth(), 1);
  }
  updateDatePicker();
  if (state.view === 'week') {
    renderWeekView();
    showEl($('week-view'), true);
    showEl($('month-view'), false);
  } else {
    renderMonthView();
    showEl($('week-view'), false);
    showEl($('month-view'), true);
  }
}

function renderWeekView() {
  const weekStart = state.currentWeekStart;
  const days      = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const today     = new Date();
  const weekEnd   = days[6];

  // Label shows "KW XX · YYYY"
  $('current-period-label').textContent =
    'KW\u00a0' + getISOWeek(weekStart) + '\u2002' + weekStart.getFullYear();

  const grid = $('week-grid');
  grid.innerHTML = '';
  grid.style.gridTemplateColumns = 'repeat(7, minmax(0, 1fr))';

  // 7 day header cells (no corner cell)
  days.forEach(d => {
    const hd = document.createElement('div');
    hd.className = 'wg-day-header' + (isSameDay(d, today) ? ' today' : '');
    hd.innerHTML =
      '<span class="wg-day-short">' + DE_DAYS[d.getDay()] + '</span>' +
      '<span class="wg-day-date">' + d.getDate() + '.' + DE_MONTHS[d.getMonth()] + '</span>';
    grid.appendChild(hd);
  });

  const visibleVenues = getVisibleVenues();
  if (!state.games.length || !visibleVenues.length) {
    showEl($('no-games-msg'), true);
    showEl($('week-view'), false);
    return;
  }

  showEl($('no-games-msg'), false);

  const weekGames = [];

  visibleVenues.forEach((venue, index) => {
    const colorIndex = state.venues.findIndex(v => v.id === venue.id);
    const vColor     = VENUE_COLORS[colorIndex % VENUE_COLORS.length];

    // Full-width venue name header spanning all 7 columns
    const rowHeader = document.createElement('div');
    rowHeader.className = 'wg-venue-row-header' + (index % 2 === 0 ? ' wg-row-even' : '');
    rowHeader.innerHTML =
      '<span class="dot" style="background:' + vColor + '"></span>' +
      '<span class="wg-venue-text" title="' + escapeHtml(venue.name) + '">' + escapeHtml(venue.name) + '</span>';
    grid.appendChild(rowHeader);

    days.forEach(day => {
      const cell = document.createElement('div');
      cell.className = 'wg-cell' + (index % 2 === 0 ? ' wg-row-even' : '');

      const dayGames = state.games
        .filter(g => deriveVenueId(g) === venue.id && isSameDay(new Date(g.startDate), day))
        .sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

      dayGames.forEach(game => {
        weekGames.push(game);
        const chip = document.createElement('div');
        chip.className = 'game-chip';
        const catColor = teamCategoryColor(game);
        chip.style.background = catColor;
        chip.title = (game.time || '') + ' ' + game.homeTeam + ' \u2013 ' + game.guestTeam + (game.competition ? ' | ' + game.competition : '');

        const opponent    = getOpponent(game);
        const logoUrl     = getOpponentLogoUrl(game);
        const result      = getGameResult(game);

        const timeEl = document.createElement('div');
        timeEl.className = 'chip-time';
        timeEl.textContent = game.time || '';
        chip.appendChild(timeEl);

        if (logoUrl) {
          const img = document.createElement('img');
          img.className = 'chip-logo';
          img.src = logoUrl;
          img.alt = opponent;
          img.loading = 'lazy';
          img.addEventListener('error', () => {
            img.remove();
          });
          chip.appendChild(img);
        }

        if (result) {
          const resultEl = document.createElement('div');
          resultEl.className = 'chip-result';
          resultEl.textContent = result;
          chip.appendChild(resultEl);
        }

        chip.addEventListener('click', () => showGameModal(game));
        cell.appendChild(chip);
      });

      grid.appendChild(cell);
    });
  });

  // Legend for team categories visible in this week
  const weekView = $('week-view');
  const existingLegend = weekView.querySelector('.team-legend');
  if (existingLegend) existingLegend.remove();
  renderLegend(weekGames, weekView);
}

function renderMonthView() {
  const month    = state.currentMonth;
  const year     = month.getFullYear();
  const monthIdx = month.getMonth();

  $('current-period-label').textContent = DE_MONTHS_LONG[monthIdx] + '\u00a0' + year;

  const listEl = $('month-list');
  listEl.innerHTML = '';

  const visibleIds = new Set(getVisibleVenues().map(v => v.id));

  const monthGames = state.games
    .filter(g => {
      const d = new Date(g.startDate);
      return (
        d.getFullYear() === year &&
        d.getMonth() === monthIdx &&
        visibleIds.has(deriveVenueId(g))
      );
    })
    .sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

  if (!monthGames.length) {
    showEl($('no-games-msg'), true);
    showEl($('month-view'), false);
    return;
  }

  showEl($('no-games-msg'), false);

  // Legend for team categories visible in this month (at top)
  renderLegend(monthGames, listEl);

  const byDay = new Map();
  monthGames.forEach(game => {
    const key = fmtFull(new Date(game.startDate));
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(game);
  });

  byDay.forEach((dayGames, label) => {
    const group = document.createElement('div');
    group.className = 'day-group';
    group.innerHTML = '<div class="day-group-header">' + escapeHtml(label) + '</div>';

    dayGames.forEach(game => {
      const vid      = deriveVenueId(game);
      const vColor   = venueColor(vid);
      const catColor = teamCategoryColor(game);
      const shortV   = getVenueShortNameForGame(game);
      const longV    = game.venueName || shortV;
      const opponent = getOpponent(game);
      const logoUrl  = getOpponentLogoUrl(game);
      const category = deriveTeamCategory(game);
      const item     = document.createElement('div');
      item.className = 'game-list-item game-list-item--lean';
      item.style.borderLeft = '4px solid ' + catColor;
      item.style.cursor = 'pointer';
      item.innerHTML =
        '<span class="gli-time">' + escapeHtml(game.time || '--:--') + '</span>' +
        '<span class="gli-logo gli-logo--lean-left">' +
          (logoUrl ? '<img class="gli-logo-img gli-logo-img--large" src="' + escapeHtml(logoUrl) + '" alt="' + escapeHtml(opponent) + '" loading="lazy" referrerpolicy="no-referrer">' : '') +
        '</span>' +
        '<span class="gli-main">' +
          '<span class="gli-main-top">' +
            '<span class="gli-category-chip gli-category-chip--rect" style="background:' + catColor + '">' + escapeHtml(category) + '</span>' +
            '<span class="gli-vs">vs</span>' +
            '<span class="gli-opponent">' + escapeHtml(opponent) + '</span>' +
          '</span>' +
          '<span class="gli-venue gli-venue--lean">' +
            '<span class="dot" style="background:' + vColor + '"></span>' +
            '<span class="gli-venue-short" title="' + escapeHtml(longV) + '">' + escapeHtml(shortV) + '</span>' +
            '<span class="gli-venue-long" title="' + escapeHtml(longV) + '">' + escapeHtml(longV) + '</span>' +
          '</span>' +
        '</span>';
      item.addEventListener('click', () => showGameModal(game));
      group.appendChild(item);
    });

    listEl.appendChild(group);
  });
}

// ===================== Legend =====================

function renderLegend(games, container) {
  const categories = new Map();
  games.forEach(game => {
    const cat = deriveTeamCategory(game);
    if (!categories.has(cat)) {
      categories.set(cat, TEAM_CATEGORY_COLORS[cat] || TEAM_CATEGORY_COLORS['Sonstige']);
    }
  });
  if (!categories.size) return;
  const legend = document.createElement('div');
  legend.className = 'team-legend';
  legend.innerHTML =
    '<span class="legend-label">Legende:</span>' +
    Array.from(categories.entries()).map(([cat, color]) =>
      '<span class="legend-item" style="background:' + color + '">' +
        escapeHtml(cat) +
      '</span>'
    ).join('');
  container.appendChild(legend);
}

// ===================== Game Modal =====================

function showGameModal(game) {
  const existing = document.getElementById('game-modal-overlay');
  if (existing) existing.remove();

  const category = deriveTeamCategory(game);
  const catColor = TEAM_CATEGORY_COLORS[category] || TEAM_CATEGORY_COLORS['Sonstige'];

  const overlay = document.createElement('div');
  overlay.id = 'game-modal-overlay';
  overlay.className = 'game-modal-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');

  overlay.innerHTML =
    '<div class="game-modal">' +
      '<div class="game-modal-header" style="background:' + catColor + '">' +
        '<span class="game-modal-category">' + escapeHtml(category) + '</span>' +
        '<button class="game-modal-close" aria-label="Schlie\u00dfen">&times;</button>' +
      '</div>' +
      '<div class="game-modal-body">' +
        '<div class="game-modal-teams game-modal-teams--with-logos">' +
          '<span class="game-modal-team-block">' +
            (game.homeLogoUrl ? '<img class="game-modal-team-logo" src="' + escapeHtml(game.homeLogoUrl) + '" alt="' + escapeHtml(game.homeTeam) + '" loading="lazy" referrerpolicy="no-referrer">' : '') +
            '<span class="game-modal-home">' + escapeHtml(game.homeTeam) + '</span>' +
          '</span>' +
          '<span class="game-modal-vs">vs.</span>' +
          '<span class="game-modal-team-block">' +
            (game.guestLogoUrl ? '<img class="game-modal-team-logo" src="' + escapeHtml(game.guestLogoUrl) + '" alt="' + escapeHtml(game.guestTeam) + '" loading="lazy" referrerpolicy="no-referrer">' : '') +
            '<span class="game-modal-guest">' + escapeHtml(game.guestTeam) + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="game-modal-meta">' +
          '<div class="game-modal-meta-row">\uD83D\uDCC5\u2002' + escapeHtml(fmtFull(new Date(game.startDate))) + '</div>' +
          '<div class="game-modal-meta-row">\uD83D\uDD50\u2002' + escapeHtml(game.time || '--:--') + ' Uhr</div>' +
          (game.competition ? '<div class="game-modal-meta-row">\uD83C\uDFC6\u2002' + escapeHtml(game.competition) + '</div>' : '') +
          (game.venueName ? '<div class="game-modal-meta-row">\uD83D\uDCCD\u2002' + escapeHtml(game.venueName) + '</div>' : '') +
          (game.gameUrl ? '<div class="game-modal-meta-row"><a class="game-modal-maps-link" href="' + escapeHtml(game.gameUrl) + '" target="_blank" rel="noopener noreferrer">Spiel auf fussball.de &#8599;</a></div>' : '') +
        '</div>' +
      '</div>' +
    '</div>';

  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.remove();
  });
  overlay.querySelector('.game-modal-close').addEventListener('click', () => overlay.remove());

  const escHandler = e => {
    if (e.key === 'Escape') {
      overlay.remove();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);

  document.body.appendChild(overlay);
}

// ===================== View Switching & Navigation =====================

function switchView(view) {
  state.view = view;
  saveViewCookie();
  $('view-week-btn').classList.toggle('btn-active', view === 'week');
  $('view-month-btn').classList.toggle('btn-active', view === 'month');
  renderCurrentView();
}

function navigatePrev() {
  if (state.view === 'week') {
    state.currentWeekStart = addDays(state.currentWeekStart, -7);
    checkAndExtendRange(state.currentWeekStart);
  } else {
    const m = state.currentMonth;
    state.currentMonth = new Date(m.getFullYear(), m.getMonth() - 1, 1);
    checkAndExtendRange(state.currentMonth);
  }
  renderCurrentView();
}

function navigateNext() {
  if (state.view === 'week') {
    state.currentWeekStart = addDays(state.currentWeekStart, 7);
    checkAndExtendRange(state.currentWeekStart);
  } else {
    const m = state.currentMonth;
    state.currentMonth = new Date(m.getFullYear(), m.getMonth() + 1, 1);
    checkAndExtendRange(state.currentMonth);
  }
  renderCurrentView();
}

function goToDate(dateStr) {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return;
  if (state.view === 'week') {
    state.currentWeekStart = getMonday(d);
    checkAndExtendRange(state.currentWeekStart);
  } else {
    state.currentMonth = new Date(d.getFullYear(), d.getMonth(), 1);
    checkAndExtendRange(state.currentMonth);
  }
  renderCurrentView();
}

// ===================== Event Binding =====================

function bindEvents() {
  $('club-search-btn').addEventListener('click', () => {
    const query = $('club-search-input').value.trim();
    if (query.length < 2) {
      showError('Bitte mindestens 2 Zeichen für die Vereinssuche eingeben.');
      return;
    }
    showError('');
    doClubSearch(query);
  });

  $('club-search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      $('club-search-btn').click();
    }
  });

  $('view-week-btn').addEventListener('click', () => switchView('week'));
  $('view-month-btn').addEventListener('click', () => switchView('month'));
  $('prev-period-btn').addEventListener('click', navigatePrev);
  $('next-period-btn').addEventListener('click', navigateNext);

  const picker = $('date-picker');
  if (picker) {
    picker.addEventListener('change', () => {
      if (picker.value) goToDate(picker.value);
    });
  }

  // Tooltip toggle for touch / keyboard
  document.addEventListener('click', e => {
    const btn = e.target.closest('.tooltip-btn');
    if (btn) {
      e.stopPropagation();
      const wrap = btn.closest('.tooltip-wrap');
      if (wrap) {
        const isOpen = wrap.classList.contains('tooltip-open');
        document.querySelectorAll('.tooltip-wrap.tooltip-open').forEach(w => w.classList.remove('tooltip-open'));
        if (!isOpen) wrap.classList.add('tooltip-open');
      }
      return;
    }
    document.querySelectorAll('.tooltip-wrap.tooltip-open').forEach(w => w.classList.remove('tooltip-open'));
  });
}

// ===================== Init =====================

async function init() {
  await loadAppMeta();
  loadFromCookies();
  $('club-search-input').value = '';
  const today = new Date();
  state.currentWeekStart = getMonday(today);
  state.currentMonth     = new Date(today.getFullYear(), today.getMonth(), 1);

  renderSelectedClub();
  renderRecentClubs();
  updateSectionVisibility();
  bindEvents();

  $('view-week-btn').classList.toggle('btn-active', state.view === 'week');
  $('view-month-btn').classList.toggle('btn-active', state.view === 'month');

  if (state.club && state.club.id) {
    await autoLoadGames();
  } else {
    renderVenueCheckboxes();
    renderTeamOverview();
    showEl($('no-games-msg'), true);
    $('current-period-label').textContent = '';
  }
}

init();
