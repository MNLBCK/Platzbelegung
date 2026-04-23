(function () {
  const $ = (id) => document.getElementById(id);
  let showAllHits = false;

  function buildClubUrl(clubId) {
    const id = String(clubId || '').trim();
    return id ? ('https://www.fussball.de/verein/-/id/' + encodeURIComponent(id)) : '';
  }

  function fmt(value) {
    if (!value) return '-';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('de-DE');
  }

  function setError(msg) {
    $('error').textContent = msg || '';
  }

  function renderStats(stats) {
    const body = $('stats-body');
    body.innerHTML = '';
    const clubs = stats.clubs || [];
    const totalParses = clubs.reduce((sum, club) => sum + Number(club.parses || 0), 0);

    clubs.forEach((club) => {
      const tr = document.createElement('tr');

      const nameCell = document.createElement('td');
      const clubUrl = buildClubUrl(club.id);
      if (clubUrl && club.name) {
        const link = document.createElement('a');
        link.href = clubUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = club.name;
        nameCell.appendChild(link);
      } else {
        nameCell.textContent = club.name || '-';
      }

      const idCell = document.createElement('td');
      const code = document.createElement('code');
      code.textContent = club.id || '-';
      idCell.appendChild(code);

      const parsesCell = document.createElement('td');
      parsesCell.textContent = String(club.parses || 0);

      const lastParsedCell = document.createElement('td');
      lastParsedCell.textContent = fmt(club.lastParsedAt);

      tr.appendChild(nameCell);
      tr.appendChild(idCell);
      tr.appendChild(parsesCell);
      tr.appendChild(lastParsedCell);
      body.appendChild(tr);
    });
    const training = stats.training || {};
    $('stats-meta').textContent = 'Gesamt: ' + totalParses + ' Parses, ' +
      (stats.totalClubs || clubs.length || 0) + ' Vereine, offene Trainingszeiten-Requests: ' +
      Number(training.pendingRequests || 0) + ', geparste Trainingszeiten: ' +
      Number(training.parsedSessions || 0) + ', aktualisiert: ' + fmt(stats.updatedAt);
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

  function renderConfigHits(hits) {
    const rows = parseConfigHits(hits.paths);
    const body = $('config-hits-body');
    body.innerHTML = '';

    if (!rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 3;
      td.textContent = 'Keine aufgerufenen Konfigurationen gefunden.';
      tr.appendChild(td);
      body.appendChild(tr);
    } else {
      rows.forEach((row) => {
        const tr = document.createElement('tr');

        const idCell = document.createElement('td');
        const idCode = document.createElement('code');
        idCode.textContent = row.configId;
        idCell.appendChild(idCode);

        const hitsCell = document.createElement('td');
        hitsCell.textContent = String(row.hits);

        const linkCell = document.createElement('td');
        const link = document.createElement('a');
        link.href = '/?config=' + encodeURIComponent(row.configId);
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'öffnen';
        linkCell.appendChild(link);

        tr.appendChild(idCell);
        tr.appendChild(hitsCell);
        tr.appendChild(linkCell);
        body.appendChild(tr);
      });
    }

    $('config-hits-meta').textContent = 'Gefundene Konfigurationen: ' + rows.length;
  }

  function renderHits(hits) {
    const toggle = $('hits-toggle');
    const body = $('hits-body');
    body.innerHTML = '';
    const rows = hits.paths || [];
    const visibleRows = showAllHits ? rows : rows.slice(0, 10);

    visibleRows.forEach((row) => {
      const tr = document.createElement('tr');
      const pathCell = document.createElement('td');
      const code = document.createElement('code');
      code.textContent = row.path || '/';
      pathCell.appendChild(code);

      const hitsCell = document.createElement('td');
      hitsCell.textContent = String(row.hits || 0);

      tr.appendChild(pathCell);
      tr.appendChild(hitsCell);
      body.appendChild(tr);
    });
    $('hits-meta').textContent = 'Gesamt: ' + (hits.total || 0) + ' Hits, aktualisiert: ' + fmt(hits.updatedAt);

    if (toggle) {
      if (rows.length > 10) {
        toggle.style.display = 'inline-block';
        toggle.textContent = showAllHits ? 'Weniger anzeigen' : 'Weitere anzeigen';
        toggle.onclick = () => {
          showAllHits = !showAllHits;
          renderHits(hits);
        };
      } else {
        toggle.style.display = 'none';
        toggle.onclick = null;
      }
    }
    renderConfigHits(hits);
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
    renderHits(data.pageHits || {});
    $('content').style.display = 'block';
  }

  $('load').addEventListener('click', loadDashboard);
  $('password').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      loadDashboard();
    }
  });
})();
