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

const COOKIE_CLUB    = 'pb_club';
const COOKIE_RECENT  = 'pb_recent';
const COOKIE_VENUES  = 'pb_venues';
const COOKIE_VIEW    = 'pb_view';

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
  games: [],
  venues: [],
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
  if (!fullName) return 'Unbekannt';
  const parts = fullName.split(',');
  let short = parts[0].trim();
  if (short.length > 22) short = short.substring(0, 20) + '\u2026';
  return short;
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
  const text = (game.competition || '') + ' ' + (game.homeTeam || '');
  if (/\bBambini\b/i.test(text)) return 'Bambini';
  const junioren = text.match(/\b([A-G])[-\s]Junior(?:en|innen)\b/i);
  if (junioren) return junioren[1].toUpperCase() + '-Junioren';
  const u = text.match(/\bU\s*(\d+)\b/i);
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
  if (/\bHerren\b/i.test(text))   return 'Herren';
  if (/\bDamen\b/i.test(text))    return 'Damen';
  if (/\bSenioren\b/i.test(text)) return 'Senioren';
  return 'Sonstige';
}

function teamCategoryColor(game) {
  const cat = deriveTeamCategory(game);
  return TEAM_CATEGORY_COLORS[cat] || TEAM_CATEGORY_COLORS['Sonstige'];
}

// Returns the opponent's name: tries to detect which team belongs to our club
function getOpponent(game) {
  if (!state.club) return game.guestTeam || '';
  const clubName = (state.club.name || '').toLowerCase();
  if (!clubName) return game.guestTeam || '';
  const htLow = (game.homeTeam  || '').toLowerCase();
  const gtLow = (game.guestTeam || '').toLowerCase();
  // Full club name substring match (works when club name ≥ several chars)
  if (clubName.length >= 4) {
    if (htLow.includes(clubName)) return game.guestTeam || '';
    if (gtLow.includes(clubName)) return game.homeTeam  || '';
  }
  // Fallback: use first word longer than 2 chars with word-boundary matching
  const key = clubName.split(/\s+/).find(w => w.length > 2);
  if (key) {
    const wordRe = new RegExp('(?:^|\\s)' + key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:\\s|$)');
    if (wordRe.test(htLow)) return game.guestTeam || '';
    if (wordRe.test(gtLow)) return game.homeTeam  || '';
  }
  return game.guestTeam || '';
}

// Returns the logo URL for the opponent team
function getOpponentLogoUrl(game) {
  if (!state.club) return game.guestLogoUrl || '';
  const clubName = (state.club.name || '').toLowerCase();
  if (!clubName) return game.guestLogoUrl || '';
  const htLow = (game.homeTeam  || '').toLowerCase();
  const gtLow = (game.guestTeam || '').toLowerCase();
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
  return game.guestLogoUrl || '';
}

// ===================== Cookie Persistence =====================

function loadFromCookies() {
  state.club = getCookie(COOKIE_CLUB);
  const savedView = getCookie(COOKIE_VIEW);
  if (savedView === 'week' || savedView === 'month') state.view = savedView;
  const savedVenues = getCookie(COOKIE_VENUES);
  state.selectedVenueIds = Array.isArray(savedVenues) ? savedVenues : null;
}

function saveClubCookie() {
  if (state.club) {
    setCookie(COOKIE_CLUB, state.club);
  } else {
    deleteCookie(COOKIE_CLUB);
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
    '<div class="recent-clubs-label">Zuletzt verwendet:</div>' +
    '<div class="recent-clubs-list">' +
    list.map(club =>
      '<button class="recent-club-btn' + (state.club && state.club.id === club.id ? ' recent-club-btn--active' : '') + '" type="button" data-club-id="' + escapeHtml(club.id) + '" title="' + escapeHtml(club.name) + (club.location ? ' \u00b7 ' + escapeHtml(club.location) : '') + '">' +
      '<span class="recent-club-logo-wrap">' +
      (club.logoUrl
        ? '<img class="recent-club-logo" src="' + escapeHtml(club.logoUrl) + '" alt="' + escapeHtml(club.name) + '" loading="lazy">'
        : '<span class="recent-club-logo-fallback">' + escapeHtml((club.name || '?').charAt(0).toUpperCase()) + '</span>') +
      '</span>' +
      '<span class="recent-club-name">' + escapeHtml(club.name) + '</span>' +
      '</button>'
    ).join('') +
    '</div>';
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
  saveClubCookie();
  saveRecentClub(club);
  renderSelectedClub();
  renderRecentClubs();
  $('club-search-input').value = club.name || '';
  const resultsEl = $('club-search-results');
  resultsEl.innerHTML = '';
  showEl(resultsEl, false);
  autoLoadGames();
}

function renderSelectedClub() {
  const el = $('selected-club-info');
  if (!el) return;
  const club = state.club;
  if (!club) { showEl(el, false); el.innerHTML = ''; return; }
  const logoHtml = club.logoUrl
    ? '<img class="selected-club-logo" src="' + escapeHtml(club.logoUrl) + '" alt="' + escapeHtml(club.name) + '" loading="lazy">'
    : '<span class="selected-club-logo-fallback">' + escapeHtml((club.name || '?').charAt(0).toUpperCase()) + '</span>';
  el.innerHTML =
    '<div class="selected-club-card">' +
      '<div class="selected-club-logo-wrap">' + logoHtml + '</div>' +
      '<div class="selected-club-details">' +
        '<div class="selected-club-name">' + escapeHtml(club.name) + '</div>' +
        (club.location ? '<div class="selected-club-location">' + escapeHtml(club.location) + '</div>' : '') +
        (club.url ? '<div class="selected-club-link"><a href="' + escapeHtml(club.url) + '" target="_blank" rel="noopener noreferrer">fussball.de &#8599;</a></div>' : '') +
      '</div>' +
    '</div>';
  showEl(el, true);
}

function clearClub() {
  state.club = null;
  state.games = [];
  state.venues = [];
  state.selectedVenueIds = null;
  state.loadedFrom = '';
  state.loadedTo = '';
  saveClubCookie();
  saveVenuesCookie();
  sessionStorage.removeItem(SESSION_KEY);
  renderSelectedClub();
  renderVenueCheckboxes();
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

async function autoLoadGames() {
  if (!state.club || !state.club.id) return;

  // Restore from session if same club
  const session = loadSession();
  if (session && session.clubId === state.club.id && Array.isArray(session.games) && session.games.length > 0) {
    state.games = session.games;
    state.loadedFrom = session.loadedFrom;
    state.loadedTo = session.loadedTo;
    state.venues = deriveVenuesFromGames(state.games);
    reconcileVenueSelection();
    renderVenueCheckboxes();
    renderCurrentView();
    return;
  }

  const { dateFrom, dateTo } = getDefaultDateRange();
  await fetchGames(dateFrom, dateTo);
}

async function fetchGames(dateFrom, dateTo) {
  if (!state.club || !state.club.id) return;
  showEl($('venues-loading'), true);
  showEl($('venues-empty'), false);
  showEl($('venues-error'), false);
  showError('');
  showLoading(true);
  try {
    const url =
      '/api/club-matchplan?id=' + encodeURIComponent(state.club.id) +
      '&dateFrom=' + encodeURIComponent(dateFrom) +
      '&dateTo=' + encodeURIComponent(dateTo) +
      '&matchType=1&max=100';
    const resp = await fetch(url);
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.error || 'Fehler beim Laden der Spiele');
      const errEl = $('venues-error');
      errEl.textContent = 'Fehler beim Laden der Spielstätten.';
      showEl(errEl, true);
      return;
    }
    state.games = Array.isArray(data) ? data : [];
    state.loadedFrom = dateFrom;
    state.loadedTo = dateTo;
    state.venues = deriveVenuesFromGames(state.games);
    reconcileVenueSelection();
    saveSession();
    renderVenueCheckboxes();
    renderCurrentView();
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
  if (!state.club || !state.club.id) return;
  showLoading(true);
  try {
    const url =
      '/api/club-matchplan?id=' + encodeURIComponent(state.club.id) +
      '&dateFrom=' + encodeURIComponent(newFrom) +
      '&dateTo=' + encodeURIComponent(newTo) +
      '&matchType=1&max=100';
    const resp = await fetch(url);
    const data = await resp.json();
    if (!resp.ok) return;
    const newGames = Array.isArray(data) ? data : [];
    const gameKey = g => `${g.startDate}|${g.venueId || ''}|${g.homeTeam || ''}`;
    const existingKeys = new Set(state.games.map(gameKey));
    const merged = state.games.concat(newGames.filter(g => !existingKeys.has(gameKey(g))));
    merged.sort((a, b) => new Date(a.startDate) - new Date(b.startDate));
    state.games = merged;
    state.loadedFrom = newFrom;
    state.loadedTo = newTo;
    state.venues = deriveVenuesFromGames(state.games);
    reconcileVenueSelection();
    saveSession();
    renderVenueCheckboxes();
    renderCurrentView();
  } catch (_) {
    // silent fail
  } finally {
    showLoading(false);
  }
}

function checkAndExtendRange(targetDate) {
  if (!state.club || !state.club.id || !state.loadedFrom || !state.loadedTo) return;
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
    const short   = deriveShortVenueName(venue.name);
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

        if (logoUrl) {
          const img = document.createElement('img');
          img.className = 'chip-logo';
          img.src = logoUrl;
          img.alt = opponent;
          img.loading = 'lazy';
          img.addEventListener('error', () => {
            img.remove();
            const fb = document.createElement('span');
            fb.className = 'chip-logo-fallback';
            fb.textContent = (opponent || '?').charAt(0).toUpperCase();
            chip.insertBefore(fb, chip.firstChild);
          });
          chip.appendChild(img);
        } else {
          const fallback = document.createElement('span');
          fallback.className = 'chip-logo-fallback';
          fallback.textContent = (opponent || '?').charAt(0).toUpperCase();
          chip.appendChild(fallback);
        }

        const timeEl = document.createElement('div');
        timeEl.className = 'chip-time';
        timeEl.textContent = game.time || '';
        chip.appendChild(timeEl);

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

  // Group by ISO week
  const byWeek = new Map();
  monthGames.forEach(game => {
    const d         = new Date(game.startDate);
    const weekStart = getMonday(d);
    const key       = formatInputDate(weekStart);
    if (!byWeek.has(key)) byWeek.set(key, { weekStart, games: [] });
    byWeek.get(key).games.push(game);
  });

  byWeek.forEach(({ weekStart, games }) => {
    const weekEnd    = addDays(weekStart, 6);
    const weekHeader = document.createElement('div');
    weekHeader.className = 'month-week-header';
    weekHeader.textContent =
      'KW\u00a0' + getISOWeek(weekStart) +
      ' \u00b7 ' + weekStart.getDate() + '.\u00a0' + DE_MONTHS[weekStart.getMonth()] +
      ' \u2013 ' + weekEnd.getDate() + '.\u00a0' + DE_MONTHS[weekEnd.getMonth()];
    listEl.appendChild(weekHeader);

    const byDay = new Map();
    games.forEach(game => {
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
        const shortV   = deriveShortVenueName(game.venueName || '');
        const opponent = getOpponent(game);
        const item     = document.createElement('div');
        item.className = 'game-list-item';
        item.style.borderLeft = '4px solid ' + catColor;
        item.style.cursor = 'pointer';
        item.innerHTML =
          '<span class="gli-time">' + escapeHtml(game.time || '--:--') + '</span>' +
          '<span class="gli-venue">' +
            '<span class="dot" style="background:' + vColor + '"></span>' +
            '<span title="' + escapeHtml(game.venueName || '') + '">' + escapeHtml(shortV) + '</span>' +
          '</span>' +
          '<span class="gli-teams">' +
            '<span class="gli-opponent">' + escapeHtml(opponent) + '</span>' +
          '</span>' +
          '<span class="gli-comp" style="color:' + catColor + ';font-weight:600">' + escapeHtml(game.competition || '') + '</span>';
        item.addEventListener('click', () => showGameModal(game));
        group.appendChild(item);
      });

      listEl.appendChild(group);
    });
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
        '<div class="game-modal-teams">' +
          '<span class="game-modal-home">' + escapeHtml(game.homeTeam) + '</span>' +
          '<span class="game-modal-vs">vs.</span>' +
          '<span class="game-modal-guest">' + escapeHtml(game.guestTeam) + '</span>' +
        '</div>' +
        '<div class="game-modal-meta">' +
          '<div class="game-modal-meta-row">\uD83D\uDCC5\u2002' + escapeHtml(fmtFull(new Date(game.startDate))) + '</div>' +
          '<div class="game-modal-meta-row">\uD83D\uDD50\u2002' + escapeHtml(game.time || '--:--') + ' Uhr</div>' +
          (game.competition ? '<div class="game-modal-meta-row">\uD83C\uDFC6\u2002' + escapeHtml(game.competition) + '</div>' : '') +
          (game.venueName ? '<div class="game-modal-meta-row">\uD83D\uDCCD\u2002' + escapeHtml(game.venueName) + '</div>' : '') +
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
  loadFromCookies();
  $('club-search-input').value = state.club ? (state.club.name || '') : '';
  const today = new Date();
  state.currentWeekStart = getMonday(today);
  state.currentMonth     = new Date(today.getFullYear(), today.getMonth(), 1);

  renderSelectedClub();
  renderRecentClubs();
  bindEvents();

  $('view-week-btn').classList.toggle('btn-active', state.view === 'week');
  $('view-month-btn').classList.toggle('btn-active', state.view === 'month');

  if (state.club && state.club.id) {
    await autoLoadGames();
  } else {
    renderVenueCheckboxes();
    showEl($('no-games-msg'), true);
    $('current-period-label').textContent = '';
  }
}

init();
