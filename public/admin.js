(function () {
  const $ = (id) => document.getElementById(id);
  let showAllHits = false;
  let statsLimit = 10;
  const SAVED_CONFIGS_KEY = 'pb_saved_configs_v1';

  function buildClubUrl(club) {
    const id = String(club && club.id || '').trim();
    if (!id) return '';
    const url = new URL(window.location.origin + '/');
    url.searchParams.set('clubId', id);
    if (club && club.name) url.searchParams.set('clubName', String(club.name));
    if (club && club.logoUrl) url.searchParams.set('clubLogoUrl', String(club.logoUrl));
    if (club && club.location) url.searchParams.set('clubLocation', String(club.location));
    return url.toString();
  }

  function readSavedConfigs() {
    try {
      const raw = window.localStorage.getItem(SAVED_CONFIGS_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function fmt(value) {
    if (!value) return '-';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('de-DE');
  }

  function setError(msg) {
    $('error').textContent = msg || '';
  }

  function renderStats(stats, hits) {
    const body = $('stats-body');
    body.innerHTML = '';
    const clubs = stats.clubs || [];
    const totalParses = clubs.reduce((sum, club) => sum + Number(club.parses || 0), 0);
    const configHits = parseConfigHits((hits && hits.paths) || []);
    const savedConfigs = readSavedConfigs();
    const savedConfigIds = Object.keys(savedConfigs);
    const mergedConfigIds = Array.from(new Set(savedConfigIds.concat(configHits.map(c => c.configId)))).sort();

    const clubRows = clubs.map((club) => {
      const tr = document.createElement('tr');

      const nameCell = document.createElement('td');
      const clubUrl = buildClubUrl(club);
      if (clubUrl && club.name) {
        const link = document.createElement('a');
        link.href = clubUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = club.name;
        nameCell.appendChild(link);
      } else {
        nameCell.textContent = club.name || club.id || '-';
      }

      const parsesCell = document.createElement('td');
      parsesCell.textContent = String(club.parses || 0) + ' Parses';

      const trainingCell = document.createElement('td');
      trainingCell.textContent = String(club.trainingRequested || 0) + ' / ' + String(club.trainingParsed || 0);

      const lastParsedCell = document.createElement('td');
      lastParsedCell.textContent = fmt(club.lastParsedAt);

      tr.appendChild(nameCell);
      tr.appendChild(parsesCell);
      tr.appendChild(trainingCell);
      tr.appendChild(lastParsedCell);
      return { activity: Number(club.parses || 0), row: tr };
    });

    const filterRows = mergedConfigIds.map((configId) => {
      const tr = document.createElement('tr');

      const entryCell = document.createElement('td');
      const link = document.createElement('a');
      link.href = '/?config=' + encodeURIComponent(configId);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = configId;
      entryCell.appendChild(link);

      const cfg = savedConfigs[configId] || {};
      const clubNames = [];
      if (cfg.club && (cfg.club.name || cfg.club.id)) clubNames.push(cfg.club.name || cfg.club.id);
      if (Array.isArray(cfg.additionalClubs)) {
        cfg.additionalClubs.forEach((c) => clubNames.push((c && (c.name || c.id)) || ''));
      }
      if (clubNames.filter(Boolean).length) {
        const hint = document.createElement('span');
        hint.style.marginLeft = '6px';
        hint.textContent = '· ' + clubNames.filter(Boolean).join(' + ');
        entryCell.appendChild(hint);
      }

      const hit = configHits.find((row) => row.configId === configId);
      const activityCell = document.createElement('td');
      activityCell.textContent = String(hit ? hit.hits : 0) + ' Aufrufe';

      const trainingCell = document.createElement('td');
      trainingCell.textContent = '-';

      const lastCell = document.createElement('td');
      lastCell.textContent = fmt(cfg.updatedAt || null);

      tr.appendChild(entryCell);
      tr.appendChild(activityCell);
      tr.appendChild(trainingCell);
      tr.appendChild(lastCell);
      return { activity: Number(hit ? hit.hits : 0), row: tr };
    });

    const appendGroup = (items, addSeparator = false) => {
      const sorted = items.sort((a, b) => b.activity - a.activity).slice(0, statsLimit);
      sorted.forEach((item, idx) => {
        if (addSeparator && idx === 0) item.row.classList.add('group-sep');
        body.appendChild(item.row);
      });
    };

    appendGroup(clubRows);
    appendGroup(filterRows, true);

    const training = stats.training || {};
    $('kpi-parses').textContent = String(totalParses);
    $('kpi-clubs').textContent = String(stats.totalClubs || clubs.length || 0);
    $('kpi-filters').textContent = String(mergedConfigIds.length);
    $('kpi-training-requests').textContent = String(training.pendingRequests || 0);
    $('kpi-training-parsed').textContent = String(training.parsedSessions || 0);

  }

  function parseConfigHits(paths) {
    const counts = new Map();
    (paths || []).forEach((row) => {
      const rawPath = String(row.path || '');
      const hits = Number(row.hits || 0);
      let url;
      try {
        url = new URL(rawPath, window.location.origin);
      } catch (e) {
        return;
      }
      const configId = (url.searchParams.get('config') || '').trim();
      if (!configId) return;
      counts.set(configId, (counts.get(configId) || 0) + hits);
    });
    return Array.from(counts.entries())
      .map(([configId, hits]) => ({ configId, hits }))
      .sort((a, b) => b.hits - a.hits || a.configId.localeCompare(b.configId));
  }


  async function loadDashboard() {
    const password = $('password').value.trim();
    if (!password) {
      setError('Bitte Passwort eingeben.');
      return;
    }
    setError('');

    const url = '/api/admin/dashboard?password=' + encodeURIComponent(password);
    let response;
    try {
      response = await fetch(url, { headers: { Accept: 'application/json' } });
    } catch (e) {
      setError('Netzwerkfehler beim Laden der Admin-Daten.');
      return;
    }

    let data = {};
    try {
      data = await response.json();
    } catch (e) {
      setError('Ungültige Server-Antwort.');
      return;
    }

    if (!response.ok) {
      setError(data.error || ('Fehler: HTTP ' + response.status));
      return;
    }

    renderStats(data.stats || {});
    $('config-json').textContent = JSON.stringify(data.config || {}, null, 2);
    $('content').style.display = 'block';
  }

  const statsLimitEl = $('stats-limit');
  if (statsLimitEl) {
    statsLimitEl.addEventListener('change', () => {
      statsLimit = Number(statsLimitEl.value || 10);
      $('load').click();
    });
  }

  $('load').addEventListener('click', loadDashboard);
  $('password').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      loadDashboard();
    }
  });
})();
