const state = {
  club: null,
  games: [],
  venues: [],
  currentWeekStart: null,
  view: 'week',
  dateFrom: '',
  dateTo: '',
};

const STORAGE_KEY = 'platzbelegung_state_v2';
const VENUE_COLORS = [
  '#1565c0', '#6a1b9a', '#e65100', '#00695c',
  '#283593', '#558b2f', '#c62828', '#4527a0',
  '#0277bd', '#2e7d32',
];
const DE_DAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
const DE_DAYS_LONG = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
const DE_MONTHS = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];
const DE_MONTHS_LONG = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];

const $ = id => document.getElementById(id);

function showEl(el, show = true) {
  if (!el) return;
  el.classList.toggle('hidden', !show);
}

function showLoading(on) {
  showEl($('loading-indicator'), on);
}

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
  return {
    dateFrom: '2026-05-01',
    dateTo: '2026-05-31',
  };
}

function loadState() {
  const defaults = getDefaultDateRange();
  state.dateFrom = defaults.dateFrom;
  state.dateTo = defaults.dateTo;

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (saved.club && saved.club.id) state.club = saved.club;
    if (saved.dateFrom) state.dateFrom = saved.dateFrom;
    if (saved.dateTo) state.dateTo = saved.dateTo;
    if (saved.view === 'list' || saved.view === 'week') state.view = saved.view;
  } catch (_) {
    // ignore invalid local state
  }
}

function saveState() {
  const payload = {
    club: state.club,
    dateFrom: state.dateFrom,
    dateTo: state.dateTo,
    view: state.view,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
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

function fmtShort(date) {
  return `${DE_DAYS[date.getDay()]} ${date.getDate()}.${DE_MONTHS[date.getMonth()]}`;
}

function fmtFull(date) {
  return `${DE_DAYS_LONG[date.getDay()]}, ${date.getDate()}. ${DE_MONTHS_LONG[date.getMonth()]} ${date.getFullYear()}`;
}

function venueColor(venueId) {
  const idx = state.venues.findIndex(v => v.id === venueId);
  return VENUE_COLORS[idx % VENUE_COLORS.length] || '#607d8b';
}

function renderSelectedClub() {
  const infoEl = $('current-club-info');
  if (!state.club || !state.club.id) {
    infoEl.textContent = '';
    showEl(infoEl, false);
    return;
  }

  const parts = [state.club.name || state.club.id];
  if (state.club.location) parts.push(state.club.location);
  infoEl.textContent = `✓ Verein: ${parts.join(' · ')}`;
  showEl(infoEl, true);
}

function renderVenueSummary() {
  const summaryEl = $('venue-summary');
  const emptyEl = $('no-venues-msg');
  const controls = $('load-controls');

  if (!state.club || !state.club.id) {
    summaryEl.innerHTML = '';
    emptyEl.textContent = 'Bitte zuerst einen Verein auswählen.';
    showEl(emptyEl, true);
    showEl(controls, false);
    return;
  }

  showEl(controls, true);
  if (state.venues.length === 0) {
    summaryEl.innerHTML = '';
    emptyEl.textContent = 'Noch keine Spielstätten geladen. Verein auswählen und "Spielplan laden" klicken.';
    showEl(emptyEl, true);
    return;
  }

  showEl(emptyEl, false);
  summaryEl.innerHTML = state.venues.map((venue, index) => `
    <div class="venue-summary-item">
      <span class="venue-color-dot" style="background:${VENUE_COLORS[index % VENUE_COLORS.length]}"></span>
      <span class="venue-name">${escapeHtml(venue.name)}</span>
    </div>
  `).join('');
}

function deriveVenuesFromGames(games) {
  const seen = new Set();
  return games.reduce((acc, game) => {
    const id = game.venueId || game.venueName || 'unbekannte-spielstaette';
    const name = game.venueName || 'Unbekannte Spielstätte';
    if (seen.has(id)) return acc;
    seen.add(id);
    acc.push({ id, name });
    return acc;
  }, []);
}

function renderClubSearchResults(clubs) {
  const resultsEl = $('club-search-results');
  if (!clubs.length) {
    resultsEl.innerHTML = '<div class="search-no-results">Keine Vereine gefunden.</div>';
    showEl(resultsEl, true);
    return;
  }

  resultsEl.innerHTML = clubs.map((club) => `
    <button class="search-result-item club-search-item" type="button" data-club-id="${escapeHtml(club.id)}">
      <span class="club-search-logo-wrap">
        ${club.logoUrl ? `<img class="club-search-logo" src="${escapeHtml(club.logoUrl)}" alt="">` : '<span class="club-search-logo club-search-logo-fallback"></span>'}
      </span>
      <span class="club-search-copy">
        <span class="search-result-name">${escapeHtml(club.name)}</span>
        <span class="search-result-loc">${escapeHtml(club.location || club.id)}</span>
      </span>
    </button>
  `).join('');

  resultsEl.querySelectorAll('[data-club-id]').forEach((button) => {
    button.addEventListener('click', () => {
      const club = clubs.find((entry) => entry.id === button.dataset.clubId);
      if (!club) return;
      state.club = club;
      saveState();
      renderSelectedClub();
      renderVenueSummary();
      $('club-search-input').value = club.name || '';
      resultsEl.innerHTML = '';
      showEl(resultsEl, false);
    });
  });
  showEl(resultsEl, true);
}

async function doClubSearch(query) {
  const directClubId = extractClubId(query);
  if (directClubId) {
    state.club = { id: directClubId, name: query.trim() };
    saveState();
    renderSelectedClub();
    renderVenueSummary();
    showEl($('club-search-results'), false);
    return;
  }

  const resultsEl = $('club-search-results');
  resultsEl.innerHTML = '<div class="search-no-results">Suche läuft…</div>';
  showEl(resultsEl, true);

  try {
    const resp = await fetch(`/api/search/clubs?q=${encodeURIComponent(query)}`);
    const data = await resp.json();
    if (!resp.ok) {
      resultsEl.innerHTML = `<div class="search-no-results">${escapeHtml(data.error || 'Fehler bei der Suche')}</div>`;
      return;
    }
    renderClubSearchResults(Array.isArray(data) ? data : []);
  } catch (err) {
    resultsEl.innerHTML = `<div class="search-no-results">Netzwerkfehler: ${escapeHtml(err.message)}</div>`;
  }
}

async function syncClubFromServer() {
  try {
    const resp = await fetch('/api/config');
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.club && data.club.id && !state.club) {
      state.club = { id: data.club.id, name: data.club.name || '' };
      saveState();
    }
  } catch (_) {
    // ignore
  }
}

async function loadGames(useDemo = false) {
  showError('');
  showLoading(true);
  showEl($('week-view'), false);
  showEl($('list-view'), false);
  showEl($('no-games-msg'), false);

  try {
    let url = '/api/demo';
    if (!useDemo) {
      if (!state.club || !state.club.id) {
        showError('Bitte zuerst einen Verein auswählen.');
        return;
      }
      state.dateFrom = $('date-from-input').value;
      state.dateTo = $('date-to-input').value;
      if (!state.dateFrom || !state.dateTo) {
        showError('Bitte Zeitraum vollständig angeben.');
        return;
      }
      saveState();
      url = `/api/club-matchplan?id=${encodeURIComponent(state.club.id)}&dateFrom=${encodeURIComponent(state.dateFrom)}&dateTo=${encodeURIComponent(state.dateTo)}&matchType=1&max=100`;
    }

    const resp = await fetch(url);
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.error || 'Fehler beim Laden der Spiele');
      return;
    }

    state.games = Array.isArray(data) ? data : [];
    state.venues = deriveVenuesFromGames(state.games);
    if (state.games.length > 0) {
      state.currentWeekStart = getMonday(new Date(state.games[0].startDate));
    }
    renderVenueSummary();
    renderCurrentView();
  } catch (err) {
    showError(`Netzwerkfehler: ${err.message}`);
  } finally {
    showLoading(false);
  }
}

function renderCurrentView() {
  if (!state.currentWeekStart) state.currentWeekStart = getMonday(new Date());
  if (state.view === 'week') renderWeekView();
  else renderListView();
}

function renderWeekView() {
  const weekStart = state.currentWeekStart;
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const today = new Date();
  const weekEnd = days[6];
  $('current-week-label').textContent =
    `${days[0].getDate()}. ${DE_MONTHS[days[0].getMonth()]} – ${weekEnd.getDate()}. ${DE_MONTHS[weekEnd.getMonth()]} ${weekEnd.getFullYear()}`;

  const grid = $('week-grid');
  grid.innerHTML = '';
  grid.style.gridTemplateColumns = '80px repeat(7, 1fr)';

  const corner = document.createElement('div');
  corner.className = 'wg-header-corner';
  grid.appendChild(corner);

  days.forEach((d) => {
    const hd = document.createElement('div');
    hd.className = `wg-day-header${isSameDay(d, today) ? ' today' : ''}`;
    hd.textContent = fmtShort(d);
    grid.appendChild(hd);
  });

  if (!state.games.length || !state.venues.length) {
    showEl($('no-games-msg'), true);
    showEl($('week-view'), false);
    return;
  }

  showEl($('no-games-msg'), false);
  showEl($('week-view'), true);

  state.venues.forEach((venue, index) => {
    const color = VENUE_COLORS[index % VENUE_COLORS.length];
    const label = document.createElement('div');
    label.className = `wg-venue-label${index % 2 === 0 ? ' wg-row-even' : ''}`;
    label.innerHTML = `<span class="dot" style="background:${color}"></span>${escapeHtml(venue.name)}`;
    grid.appendChild(label);

    days.forEach((day) => {
      const cell = document.createElement('div');
      cell.className = `wg-cell${index % 2 === 0 ? ' wg-row-even' : ''}`;

      const dayGames = state.games
        .filter((game) => {
          if (game.venueId !== venue.id) return false;
          return isSameDay(new Date(game.startDate), day);
        })
        .sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

      dayGames.forEach((game) => {
        const chip = document.createElement('div');
        chip.className = 'game-chip';
        chip.style.background = color;
        chip.innerHTML = `
          <div class="chip-time">${escapeHtml(game.time || '')}</div>
          <div class="chip-match">${escapeHtml(game.homeTeam)} – ${escapeHtml(game.guestTeam)}</div>
          <div class="chip-comp">${escapeHtml(game.competition || '')}</div>
        `;
        cell.appendChild(chip);
      });

      grid.appendChild(cell);
    });
  });
}

function renderListView() {
  const listEl = $('games-list');
  listEl.innerHTML = '';

  const weekStart = state.currentWeekStart;
  const weekEnd = addDays(weekStart, 7);
  const weekGames = state.games
    .filter((game) => {
      const date = new Date(game.startDate);
      return date >= weekStart && date < weekEnd;
    })
    .sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

  $('current-week-label').textContent =
    `${weekStart.getDate()}. ${DE_MONTHS[weekStart.getMonth()]} – ${addDays(weekStart, 6).getDate()}. ${DE_MONTHS[addDays(weekStart, 6).getMonth()]} ${addDays(weekStart, 6).getFullYear()}`;

  if (!weekGames.length) {
    showEl($('no-games-msg'), true);
    showEl($('list-view'), false);
    return;
  }

  showEl($('no-games-msg'), false);
  showEl($('list-view'), true);

  const byDay = new Map();
  weekGames.forEach((game) => {
    const key = fmtFull(new Date(game.startDate));
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(game);
  });

  byDay.forEach((games, label) => {
    const group = document.createElement('div');
    group.className = 'day-group';
    group.innerHTML = `<div class="day-group-header">${escapeHtml(label)}</div>`;

    games.forEach((game) => {
      const item = document.createElement('div');
      item.className = 'game-list-item';
      item.innerHTML = `
        <span class="gli-time">${escapeHtml(game.time || '--:--')}</span>
        <span class="gli-venue">
          <span class="dot" style="background:${venueColor(game.venueId)}"></span>
          ${escapeHtml(game.venueName || 'Unbekannte Spielstätte')}
        </span>
        <span class="gli-match">${escapeHtml(game.homeTeam)}</span>
        <span class="gli-vs">vs. ${escapeHtml(game.guestTeam)}</span>
        <span class="gli-comp">${escapeHtml(game.competition || '')}</span>
      `;
      group.appendChild(item);
    });

    listEl.appendChild(group);
  });
}

function switchView(view) {
  state.view = view;
  saveState();
  $('view-week-btn').classList.toggle('btn-active', view === 'week');
  $('view-list-btn').classList.toggle('btn-active', view === 'list');
  renderCurrentView();
}

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

  $('club-search-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      $('club-search-btn').click();
    }
  });

  $('load-games-btn').addEventListener('click', () => loadGames(false));
  $('demo-btn').addEventListener('click', () => loadGames(true));
  $('clear-club-btn').addEventListener('click', () => {
    state.club = null;
    state.games = [];
    state.venues = [];
    saveState();
    renderSelectedClub();
    renderVenueSummary();
    $('club-search-input').value = '';
    $('games-list').innerHTML = '';
    $('week-grid').innerHTML = '';
    showEl($('week-view'), false);
    showEl($('list-view'), false);
    showEl($('no-games-msg'), true);
  });

  $('view-week-btn').addEventListener('click', () => switchView('week'));
  $('view-list-btn').addEventListener('click', () => switchView('list'));
  $('prev-week-btn').addEventListener('click', () => {
    state.currentWeekStart = addDays(state.currentWeekStart, -7);
    renderCurrentView();
  });
  $('next-week-btn').addEventListener('click', () => {
    state.currentWeekStart = addDays(state.currentWeekStart, 7);
    renderCurrentView();
  });
  $('today-btn').addEventListener('click', () => {
    state.currentWeekStart = getMonday(new Date());
    renderCurrentView();
  });
}

async function init() {
  loadState();
  await syncClubFromServer();
  $('date-from-input').value = state.dateFrom;
  $('date-to-input').value = state.dateTo;
  state.currentWeekStart = getMonday(new Date());
  renderSelectedClub();
  renderVenueSummary();
  bindEvents();
  switchView(state.view);
}

init();
