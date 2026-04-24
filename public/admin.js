(function () {
  const $ = (id) => document.getElementById(id);
  let statsLimit = 10;
  let sharedConfigs = [];

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

  function fmt(value) {
    if (!value) return '-';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('de-DE');
  }

  function setError(msg) {
    $('error').textContent = msg || '';
  }

  function configClubLabel(cfg) {
    const names = [];
    if (cfg.club && (cfg.club.name || cfg.club.id)) names.push(cfg.club.name || cfg.club.id);
    if (Array.isArray(cfg.additionalClubs)) {
      cfg.additionalClubs.forEach((club) => {
        if (club && (club.name || club.id)) names.push(club.name || club.id);
      });
    }
    return names.join(', ');
  }

  function renderStats(stats) {
    const body = $('stats-body');
    body.innerHTML = '';
    const clubs = stats.clubs || [];
    const totalParses = clubs.reduce((sum, club) => sum + Number(club.parses || 0), 0);

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

    const sorted = clubRows.sort((a, b) => b.activity - a.activity).slice(0, statsLimit);
    sorted.forEach((item) => body.appendChild(item.row));

    const training = stats.training || {};
    $('kpi-parses').textContent = String(totalParses);
    $('kpi-clubs').textContent = String(stats.totalClubs || clubs.length || 0);
    $('kpi-filters').textContent = String(sharedConfigs.length);
    $('kpi-training-requests').textContent = String(training.pendingRequests || 0);
    $('kpi-training-parsed').textContent = String(training.parsedSessions || 0);
  }

  function renderSharedConfigsTable() {
    const body = $('shared-configs-body');
    body.innerHTML = '';

    if (!sharedConfigs.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 6;
      td.textContent = 'Keine serverseitig gespeicherten Konfigurationen.';
      tr.appendChild(td);
      body.appendChild(tr);
      return;
    }

    sharedConfigs.forEach((cfg) => {
      const tr = document.createElement('tr');

      const idCell = document.createElement('td');
      const link = document.createElement('a');
      link.href = '/?config=' + encodeURIComponent(cfg.id);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = cfg.id;
      idCell.appendChild(link);

      const clubsCell = document.createElement('td');
      clubsCell.textContent = configClubLabel(cfg) || '-';

      const hitsCell = document.createElement('td');
      hitsCell.textContent = String(cfg.hits || 0);

      const updatedCell = document.createElement('td');
      updatedCell.textContent = fmt(cfg.updatedAt);

      const actionsCell = document.createElement('td');
      const renameBtn = document.createElement('button');
      renameBtn.type = 'button';
      renameBtn.className = 'btn-secondary';
      renameBtn.textContent = 'ID umbenennen';
      renameBtn.addEventListener('click', () => renameConfigId(cfg));

      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'btn-danger';
      deleteBtn.textContent = 'Löschen';
      deleteBtn.style.marginLeft = '6px';
      deleteBtn.addEventListener('click', () => deleteConfig(cfg));

      actionsCell.appendChild(renameBtn);
      actionsCell.appendChild(deleteBtn);

      tr.appendChild(idCell);
      tr.appendChild(clubsCell);
      tr.appendChild(hitsCell);
      tr.appendChild(updatedCell);
      tr.appendChild(actionsCell);
      body.appendChild(tr);
    });
  }

  async function renameConfigId(cfg) {
    const password = $('password').value.trim();
    if (!password) {
      setError('Bitte Passwort eingeben.');
      return;
    }
    const nextId = window.prompt('Neue ID für ' + cfg.id, cfg.id);
    if (nextId === null) return;
    const clean = String(nextId).trim().toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12);
    if (!clean) {
      setError('Neue ID ist ungültig.');
      return;
    }
    try {
      const resp = await fetch('/api/admin/shared-config?id=' + encodeURIComponent(cfg.id) + '&password=' + encodeURIComponent(password), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newId: clean }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setError(data.error || 'ID-Umbenennung fehlgeschlagen.');
        return;
      }
      await loadDashboard();
    } catch (e) {
      setError('Netzwerkfehler beim ID-Umbenennen.');
    }
  }

  async function deleteConfig(cfg) {
    const password = $('password').value.trim();
    if (!password) {
      setError('Bitte Passwort eingeben.');
      return;
    }
    if (!window.confirm('Konfiguration ' + cfg.id + ' wirklich löschen?')) {
      return;
    }
    try {
      const resp = await fetch('/api/admin/shared-config?id=' + encodeURIComponent(cfg.id) + '&password=' + encodeURIComponent(password), {
        method: 'DELETE',
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setError(data.error || 'Löschen fehlgeschlagen.');
        return;
      }
      await loadDashboard();
    } catch (e) {
      setError('Netzwerkfehler beim Löschen.');
    }
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

    sharedConfigs = Array.isArray(data.sharedConfigs) ? data.sharedConfigs : [];
    renderStats(data.stats || {});
    renderSharedConfigsTable();
    $('content').style.display = 'block';
  }

  const statsLimitEl = $('stats-limit');
  if (statsLimitEl) {
    statsLimitEl.addEventListener('change', () => {
      statsLimit = Number(statsLimitEl.value || 10);
      renderStats({ clubs: [], training: {} });
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
