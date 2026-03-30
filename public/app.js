/* global state */
const state = {
  venues: [],        // [{id, name}]
  games: [],         // fetched game objects
  currentWeekStart: null, // Monday of displayed week
  view: 'week',      // 'week' | 'list'
};

const VENUE_COLORS = [
  '#1565c0', '#6a1b9a', '#e65100', '#00695c',
  '#283593', '#558b2f', '#c62828', '#4527a0',
  '#0277bd', '#2e7d32',
];

// ─── Persistence ────────────────────────────────────────────────────────────
function loadState() {
  try {
    const saved = localStorage.getItem('platzbelegung_venues');
    if (saved) state.venues = JSON.parse(saved);
  } catch (_) { /* ignore */ }
}

function saveState() {
  try {
    localStorage.setItem('platzbelegung_venues', JSON.stringify(state.venues));
  } catch (_) { /* ignore */ }
}

// ─── Utility ────────────────────────────────────────────────────────────────
function getMonday(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = (day === 0 ? -6 : 1 - day);
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

const DE_DAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
const DE_DAYS_LONG = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
const DE_MONTHS = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];
const DE_MONTHS_LONG = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];

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

function extractVenueId(input) {
  input = input.trim();
  // Handle full fussball.de URL
  const match = input.match(/\/id\/([^/?#]+)/);
  if (match) return match[1];
  return input;
}

// ─── DOM helpers ────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
function showEl(el, show = true) {
  if (show) el.classList.remove('hidden');
  else el.classList.add('hidden');
}

function showError(msg) {
  const el = $('error-msg');
  el.textContent = msg;
  showEl(el, !!msg);
}

function showLoading(on) {
  showEl($('loading-indicator'), on);
}

// ─── Venues List ────────────────────────────────────────────────────────────
function renderVenuesList() {
  const ul = $('venues-ul');
  const noMsg = $('no-venues-msg');
  const controls = $('load-controls');

  ul.innerHTML = '';
  if (state.venues.length === 0) {
    showEl(noMsg, true);
    showEl(controls, false);
    return;
  }
  showEl(noMsg, false);
  showEl(controls, true);

  state.venues.forEach((v, i) => {
    const li = document.createElement('li');
    const color = VENUE_COLORS[i % VENUE_COLORS.length];
    li.innerHTML = `
      <span class="venue-color-dot" style="background:${color}"></span>
      <span class="venue-name">${escapeHtml(v.name)}</span>
      <span class="venue-id">${escapeHtml(v.id)}</span>
      <button class="btn-remove" data-id="${escapeAttr(v.id)}" title="Entfernen">✕</button>
    `;
    ul.appendChild(li);
  });
}

function addVenue(id, name) {
  if (!id) return;
  if (state.venues.some(v => v.id === id)) {
    alert(`Platz „${name || id}" ist bereits in der Liste.`);
    return;
  }
  state.venues.push({ id, name: name || id });
  saveState();
  renderVenuesList();
}

function removeVenue(id) {
  state.venues = state.venues.filter(v => v.id !== id);
  saveState();
  renderVenuesList();
  // Remove games for this venue and refresh display
  state.games = state.games.filter(g => g.venueId !== id);
  renderCurrentView();
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ─── Search ─────────────────────────────────────────────────────────────────
async function doSearch(query) {
  const resultsEl = $('search-results');
  resultsEl.innerHTML = '';
  showEl(resultsEl, true);

  try {
    const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await resp.json();

    if (!resp.ok) {
      resultsEl.innerHTML = `<div class="search-no-results">${escapeHtml(data.error || 'Fehler bei der Suche')}</div>`;
      return;
    }

    if (!Array.isArray(data) || data.length === 0) {
      resultsEl.innerHTML = '<div class="search-no-results">Keine Sportplätze gefunden.</div>';
      return;
    }

    data.forEach(venue => {
      const item = document.createElement('div');
      item.className = 'search-result-item';
      item.innerHTML = `
        <div class="search-result-name">${escapeHtml(venue.name)}</div>
        <div class="search-result-loc">${escapeHtml(venue.location || venue.id)}</div>
      `;
      item.addEventListener('click', () => {
        addVenue(venue.id, venue.name);
        resultsEl.innerHTML = '';
        showEl(resultsEl, false);
        $('search-input').value = '';
      });
      resultsEl.appendChild(item);
    });
  } catch (err) {
    resultsEl.innerHTML = `<div class="search-no-results">Netzwerkfehler: ${escapeHtml(err.message)}</div>`;
  }
}

// ─── Load Games ─────────────────────────────────────────────────────────────
async function loadGames(useDemo = false) {
  showError('');
  showLoading(true);
  showEl($('week-view'), false);
  showEl($('list-view'), false);
  showEl($('no-games-msg'), false);

  try {
    let url;
    if (useDemo) {
      url = '/api/demo';
    } else {
      const params = state.venues.map(v => `venueId=${encodeURIComponent(v.id)}`).join('&');
      url = `/api/games?${params}`;
    }

    const resp = await fetch(url);
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.error || 'Fehler beim Laden der Spiele');
      return;
    }

    state.games = Array.isArray(data) ? data : [];

    // If demo, also populate venues from the data
    if (useDemo) {
      const seen = new Set();
      state.games.forEach(g => {
        if (!seen.has(g.venueId)) {
          seen.add(g.venueId);
          if (!state.venues.some(v => v.id === g.venueId)) {
            state.venues.push({ id: g.venueId, name: g.venueName || g.venueId });
          }
        }
      });
      saveState();
      renderVenuesList();
    }

    renderCurrentView();
  } catch (err) {
    showError(`Netzwerkfehler: ${err.message}`);
  } finally {
    showLoading(false);
  }
}

// ─── Rendering ──────────────────────────────────────────────────────────────
function renderCurrentView() {
  if (state.view === 'week') renderWeekView();
  else renderListView();
}

function renderWeekView() {
  const weekStart = state.currentWeekStart;
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const today = new Date();

  // Update week label
  const weekEnd = days[6];
  $('current-week-label').textContent =
    `${days[0].getDate()}. ${DE_MONTHS[days[0].getMonth()]} – ${weekEnd.getDate()}. ${DE_MONTHS[weekEnd.getMonth()]} ${weekEnd.getFullYear()}`;

  const grid = $('week-grid');
  grid.innerHTML = '';

  // Column count = 1 (venue labels) + 7 (days)
  grid.style.gridTemplateColumns = `80px repeat(7, 1fr)`;

  // Header row: corner + day headers
  const corner = document.createElement('div');
  corner.className = 'wg-header-corner';
  grid.appendChild(corner);

  days.forEach(d => {
    const hd = document.createElement('div');
    hd.className = 'wg-day-header' + (isSameDay(d, today) ? ' today' : '');
    hd.textContent = fmtShort(d);
    grid.appendChild(hd);
  });

  // One row per venue
  const hasGames = state.games.length > 0;

  if (!hasGames || state.venues.length === 0) {
    showEl($('no-games-msg'), true);
    showEl($('week-view'), false);
    return;
  }

  showEl($('no-games-msg'), false);
  showEl($('week-view'), true);

  state.venues.forEach((venue, i) => {
    const color = VENUE_COLORS[i % VENUE_COLORS.length];

    // Venue label cell
    const lbl = document.createElement('div');
    lbl.className = 'wg-venue-label';
    lbl.innerHTML = `<span class="dot" style="background:${color}"></span>${escapeHtml(venue.name)}`;
    grid.appendChild(lbl);

    // Day cells
    days.forEach(day => {
      const cell = document.createElement('div');
      cell.className = 'wg-cell';

      const dayGames = state.games.filter(g => {
        if (g.venueId !== venue.id) return false;
        const gd = new Date(g.startDate);
        return isSameDay(gd, day);
      }).sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

      dayGames.forEach(g => {
        const chip = document.createElement('div');
        chip.className = 'game-chip';
        chip.style.background = color;
        chip.innerHTML = `
          <div class="chip-time">${escapeHtml(g.time || '')}</div>
          <div class="chip-match">${escapeHtml(g.homeTeam)} – ${escapeHtml(g.guestTeam)}</div>
          <div class="chip-comp">${escapeHtml(g.competition || '')}</div>
        `;
        chip.title = `${g.date} ${g.time}\n${g.homeTeam} – ${g.guestTeam}\n${g.competition}`;
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
    .filter(g => {
      const d = new Date(g.startDate);
      return d >= weekStart && d < weekEnd;
    })
    .sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

  // Update week label
  $('current-week-label').textContent =
    `${weekStart.getDate()}. ${DE_MONTHS[weekStart.getMonth()]} – ${addDays(weekStart, 6).getDate()}. ${DE_MONTHS[addDays(weekStart, 6).getMonth()]} ${addDays(weekStart, 6).getFullYear()}`;

  if (weekGames.length === 0) {
    showEl($('no-games-msg'), true);
    showEl($('list-view'), false);
    return;
  }

  showEl($('no-games-msg'), false);
  showEl($('list-view'), true);

  // Group by day
  const byDay = new Map();
  weekGames.forEach(g => {
    const d = new Date(g.startDate);
    const key = fmtFull(d);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(g);
  });

  byDay.forEach((games, dayLabel) => {
    const group = document.createElement('div');
    group.className = 'day-group';

    const header = document.createElement('div');
    header.className = 'day-group-header';
    header.textContent = dayLabel;
    group.appendChild(header);

    games.forEach(g => {
      const venueIdx = state.venues.findIndex(v => v.id === g.venueId);
      const color = VENUE_COLORS[venueIdx >= 0 ? venueIdx % VENUE_COLORS.length : 0];

      const item = document.createElement('div');
      item.className = 'game-list-item';
      item.innerHTML = `
        <span class="gli-time">${escapeHtml(g.time || '--:--')}</span>
        <span class="gli-venue">
          <span class="dot" style="background:${color}"></span>
          ${escapeHtml(g.venueName || g.venueId)}
        </span>
        <span class="gli-match">${escapeHtml(g.homeTeam)}</span>
        <span class="gli-vs">vs. ${escapeHtml(g.guestTeam)}</span>
        <span class="gli-comp">${escapeHtml(g.competition || '')}</span>
      `;
      group.appendChild(item);
    });

    listEl.appendChild(group);
  });
}

// ─── View Switching ──────────────────────────────────────────────────────────
function switchView(view) {
  state.view = view;
  $('view-week-btn').classList.toggle('btn-active', view === 'week');
  $('view-list-btn').classList.toggle('btn-active', view === 'list');
  showEl($('week-view'), false);
  showEl($('list-view'), false);
  renderCurrentView();
}

// ─── Event Wiring ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadState();
  state.currentWeekStart = getMonday(new Date());
  renderVenuesList();

  // Search
  $('search-btn').addEventListener('click', () => {
    const q = $('search-input').value.trim();
    if (q.length >= 2) doSearch(q);
  });
  $('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const q = $('search-input').value.trim();
      if (q.length >= 2) doSearch(q);
    }
  });

  // Manual add
  $('add-venue-btn').addEventListener('click', () => {
    const raw = $('venue-id-input').value.trim();
    if (!raw) { alert('Bitte eine Sportstätten-ID oder URL eingeben.'); return; }
    const id = extractVenueId(raw);
    const name = $('venue-name-input').value.trim() || id;
    if (!id) { alert('Ungültige Eingabe.'); return; }
    addVenue(id, name);
    $('venue-id-input').value = '';
    $('venue-name-input').value = '';
  });

  // Remove venues (event delegation)
  $('venues-ul').addEventListener('click', e => {
    const btn = e.target.closest('.btn-remove');
    if (btn) removeVenue(btn.dataset.id);
  });

  // Clear all
  $('clear-venues-btn').addEventListener('click', () => {
    if (confirm('Alle Sportplätze entfernen?')) {
      state.venues = [];
      state.games = [];
      saveState();
      renderVenuesList();
      renderCurrentView();
    }
  });

  // Load games
  $('load-games-btn').addEventListener('click', () => {
    if (state.venues.length === 0) {
      alert('Bitte zuerst mindestens einen Sportplatz hinzufügen.');
      return;
    }
    loadGames(false);
  });

  // Demo
  $('demo-btn').addEventListener('click', () => loadGames(true));

  // Week navigation
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

  // View toggle
  $('view-week-btn').addEventListener('click', () => switchView('week'));
  $('view-list-btn').addEventListener('click', () => switchView('list'));

  // Hide search results on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.search-section')) {
      showEl($('search-results'), false);
    }
  });
});
