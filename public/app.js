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

function showEl(el, show) {
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
  const infoEl = $('current-club-info');
  if (!state.club || !state.club.id) {
    infoEl.innerHTML = '';
    showEl(infoEl, false);
    return;
  }
  const nameParts = [state.club.name || state.club.id];
  if (state.club.location) nameParts.push(state.club.location);
  const label = nameParts.join(' \u00b7 ');
  infoEl.innerHTML =
    '<span class="current-club-check">\u2713</span>' +
    (state.club.logoUrl
      ? '<img class="current-club-logo" src="' + escapeHtml(state.club.logoUrl) + '" alt="' + escapeHtml(state.club.name || '') + '">'
      : '') +
    '<span class="current-club-name">' + escapeHtml(label) + '</span>' +
    '<button class="btn btn-sm btn-secondary clear-club-inline" type="button" aria-label="Verein entfernen">\u2715</button>';
  showEl(infoEl, true);
  infoEl.querySelector('.clear-club-inline').addEventListener('click', clearClub);
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
    const gameKey = g => JSON.stringify([g.startDate, g.venueId, g.homeTeam]);
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

  cbEl.innerHTML = state.venues.map((venue, index) => {
    const color   = VENUE_COLORS[index % VENUE_COLORS.length];
    const checked = isVenueSelected(venue.id) ? 'checked' : '';
    const short   = deriveShortVenueName(venue.name);
    return (
      '<label class="venue-checkbox-item">' +
      '<input type="checkbox" data-venue-id="' + escapeHtml(venue.id) + '" ' + checked + ' />' +
      '<span class="venue-color-dot" style="background:' + color + '"></span>' +
      '<span class="venue-short-name">' + escapeHtml(short) + '</span>' +
      '<span class="venue-full-name" title="' + escapeHtml(venue.name) + '">' + escapeHtml(venue.name) + '</span>' +
      '</label>'
    );
  }).join('');

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

  $('current-period-label').textContent =
    'KW\u00a0' + getISOWeek(weekStart) +
    ' \u00b7 ' + days[0].getDate() + '.\u00a0' + DE_MONTHS[days[0].getMonth()] +
    ' \u2013 ' + weekEnd.getDate() + '.\u00a0' + DE_MONTHS[weekEnd.getMonth()] +
    '\u00a0' + weekEnd.getFullYear();

  const grid = $('week-grid');
  grid.innerHTML = '';
  grid.style.gridTemplateColumns = '56px repeat(7, 1fr)';

  const corner = document.createElement('div');
  corner.className = 'wg-header-corner';
  grid.appendChild(corner);

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

  visibleVenues.forEach((venue, index) => {
    const colorIndex = state.venues.findIndex(v => v.id === venue.id);
    const color      = VENUE_COLORS[colorIndex % VENUE_COLORS.length];
    const shortName  = deriveShortVenueName(venue.name);
    const label      = document.createElement('div');
    label.className  = 'wg-venue-label' + (index % 2 === 0 ? ' wg-row-even' : '');
    label.innerHTML  =
      '<span class="dot" style="background:' + color + '"></span>' +
      '<span class="wg-venue-text" title="' + escapeHtml(venue.name) + '">' + escapeHtml(shortName) + '</span>';
    grid.appendChild(label);

    days.forEach(day => {
      const cell = document.createElement('div');
      cell.className = 'wg-cell' + (index % 2 === 0 ? ' wg-row-even' : '');

      const dayGames = state.games
        .filter(g => deriveVenueId(g) === venue.id && isSameDay(new Date(g.startDate), day))
        .sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

      dayGames.forEach(game => {
        const chip = document.createElement('div');
        chip.className = 'game-chip';
        chip.style.background = color;
        chip.innerHTML =
          '<div class="chip-time">' + escapeHtml(game.time || '') + '</div>' +
          '<div class="chip-match">' + escapeHtml(game.homeTeam) + ' \u2013 ' + escapeHtml(game.guestTeam) + '</div>' +
          '<div class="chip-comp">' + escapeHtml(game.competition || '') + '</div>';
        cell.appendChild(chip);
      });

      grid.appendChild(cell);
    });
  });
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
        const color    = venueColor(vid);
        const shortV   = deriveShortVenueName(game.venueName || '');
        const item     = document.createElement('div');
        item.className = 'game-list-item';
        item.innerHTML =
          '<span class="gli-time">' + escapeHtml(game.time || '--:--') + '</span>' +
          '<span class="gli-venue">' +
            '<span class="dot" style="background:' + color + '"></span>' +
            '<span title="' + escapeHtml(game.venueName || '') + '">' + escapeHtml(shortV) + '</span>' +
          '</span>' +
          '<span class="gli-teams">' +
            '<span class="gli-home">' + escapeHtml(game.homeTeam) + '</span>' +
            '<span class="gli-vs">vs.</span>' +
            '<span class="gli-guest">' + escapeHtml(game.guestTeam) + '</span>' +
          '</span>' +
          '<span class="gli-comp">' + escapeHtml(game.competition || '') + '</span>';
        group.appendChild(item);
      });

      listEl.appendChild(group);
    });
  });
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
    if (e.key === 'Enter') { e.preventDefault(); $('club-search-btn').click(); }
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
