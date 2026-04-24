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

      const nameCell = document.createElement('td');
      nameCell.textContent = club.name || '-';

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
    $('stats-meta').textContent = 'Gesamt: ' + (stats.totalParses || 0) + ' Parses, ' +
      (stats.totalClubs || 0) + ' Vereine, aktualisiert: ' + fmt(stats.updatedAt);
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

  $('load').addEventListener('click', loadDashboard);
  $('password').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      loadDashboard();
    }
  });
})();
