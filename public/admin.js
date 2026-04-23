(function () {
  const $ = (id) => document.getElementById(id);

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
    (stats.clubs || []).forEach((club) => {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td>' + (club.name || '-') + '</td>' +
        '<td><code>' + (club.id || '-') + '</code></td>' +
        '<td>' + (club.parses || 0) + '</td>' +
        '<td>' + fmt(club.lastParsedAt) + '</td>';
      body.appendChild(tr);
    });
    $('stats-meta').textContent = 'Gesamt: ' + (stats.totalParses || 0) + ' Parses, ' +
      (stats.totalClubs || 0) + ' Vereine, aktualisiert: ' + fmt(stats.updatedAt);
  }

  function renderHits(hits) {
    const body = $('hits-body');
    body.innerHTML = '';
    (hits.paths || []).forEach((row) => {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td><code>' + (row.path || '/') + '</code></td><td>' + (row.hits || 0) + '</td>';
      body.appendChild(tr);
    });
    $('hits-meta').textContent = 'Gesamt: ' + (hits.total || 0) + ' Hits, aktualisiert: ' + fmt(hits.updatedAt);
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
    $('config-json').textContent = JSON.stringify(data.config || {}, null, 2);
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
