'use strict';

const request = require('supertest');
const axios = require('axios');
const { app, server, parseClubMatchplanHtml, searchClubs } = require('../server');

afterAll(() => server.close());
afterEach(() => jest.restoreAllMocks());

describe('GET /api/demo', () => {
  it('returns an array of game objects', async () => {
    const res = await request(app).get('/api/demo');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
  });

  it('each game has required fields', async () => {
    const res = await request(app).get('/api/demo');
    res.body.forEach(game => {
      expect(game).toHaveProperty('venueId');
      expect(game).toHaveProperty('venueName');
      expect(game).toHaveProperty('homeTeam');
      expect(game).toHaveProperty('guestTeam');
      expect(game).toHaveProperty('startDate');
    });
  });

  it('startDate is a valid ISO date string', async () => {
    const res = await request(app).get('/api/demo');
    res.body.forEach(game => {
      expect(new Date(game.startDate).toString()).not.toBe('Invalid Date');
    });
  });
});

describe('GET /api/games', () => {
  it('returns 400 without venueId param', async () => {
    const res = await request(app).get('/api/games');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('rejects invalid venueId characters', async () => {
    const res = await request(app).get('/api/games?venueId=../etc/passwd');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns 404 when no snapshot exists (valid venueId)', async () => {
    // No data/latest.json present in the test environment
    const res = await request(app).get('/api/games?venueId=SOME_VALID_ID');
    // Either 404 (no snapshot) or 200 (snapshot exists) – must not be 400/500
    expect([200, 404]).toContain(res.status);
    if (res.status === 404) {
      expect(res.body).toHaveProperty('error');
    }
  });
});

describe('GET /api/snapshot', () => {
  it('returns 404 when no snapshot exists', async () => {
    const res = await request(app).get('/api/snapshot');
    // No data/latest.json in test env
    expect(res.status).toBe(404);
    expect(res.body).toHaveProperty('error');
  });
});

describe('GET /api/search', () => {
  it('returns 400 for short query', async () => {
    const res = await request(app).get('/api/search?q=A');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns 400 without query param', async () => {
    const res = await request(app).get('/api/search');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });
});

describe('Static file serving', () => {
  it('serves index.html at /', async () => {
    const res = await request(app).get('/');
    expect(res.status).toBe(200);
    expect(res.text).toContain('Platzbelegung');
  });
});

describe('GET /api/config', () => {
  it('returns 200 with club, season, and venues fields', async () => {
    const res = await request(app).get('/api/config');
    // config.yaml exists in the repo root
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('club');
    expect(res.body).toHaveProperty('season');
    expect(res.body).toHaveProperty('venues');
    expect(Array.isArray(res.body.venues)).toBe(true);
  });
});

describe('GET /api/search/clubs', () => {
  it('returns 400 for short query', async () => {
    const res = await request(app).get('/api/search/clubs?q=A');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns 400 without query param', async () => {
    const res = await request(app).get('/api/search/clubs');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('parses club search results with logo and location', async () => {
    const html = `
      <section id="club-search-results">
        <div id="clublist">
          <ul>
            <li>
              <a href="https://www.fussball.de/verein/skv-hochberg-wuerttemberg/-/id/00ES8GNAVO00000PVV0AG08LVUPGND5I" class="image-wrapper">
                <div class="image">
                  <img src="//www.fussball.de/export.media/-/action/getLogo/format/7/id/00ES8GNAVO00000PVV0AG08LVUPGND5I" alt="logo">
                </div>
                <div class="text">
                  <p class="name">SKV Hochberg<span class="icon-link-arrow"></span></p>
                  <p class="sub">71686&nbsp;Remseck am Neckar</p>
                </div>
              </a>
            </li>
          </ul>
        </div>
      </section>
    `;
    jest.spyOn(axios, 'get').mockResolvedValue({ data: html });

    const clubs = await searchClubs('skv hochberg');
    expect(clubs).toHaveLength(1);
    expect(clubs[0]).toEqual(expect.objectContaining({
      id: '00ES8GNAVO00000PVV0AG08LVUPGND5I',
      name: 'SKV Hochberg',
      location: '71686 Remseck am Neckar',
      logoUrl: 'https://www.fussball.de/export.media/-/action/getLogo/format/7/id/00ES8GNAVO00000PVV0AG08LVUPGND5I',
    }));
  });
});

describe('parseClubMatchplanHtml', () => {
  it('extracts games and venue rows from the club matchplan HTML', () => {
    const html = `
      <table class="table table-striped table-full-width">
        <tbody>
          <tr class="odd row-competition hidden-small">
            <td class="column-date"><span class="hidden-small inline">So, 10.05.26 |&nbsp;</span>15:00</td>
            <td colspan="3" class="column-team"><a>Herren | Kreisliga A; Kreisliga</a></td>
            <td colspan="2"><a>ME | 355926184</a></td>
          </tr>
          <tr class="odd">
            <td class="hidden-small"></td>
            <td class="column-club"><a class="club-wrapper"><div class="club-name">SKV Hochberg</div></a></td>
            <td class="column-colon">:</td>
            <td class="column-club no-border"><a class="club-wrapper"><div class="club-name">VfB Neckarrems 1913 e.V.</div></a></td>
            <td class="column-score"></td>
            <td class="column-detail"></td>
          </tr>
          <tr class="odd row-venue hidden-small">
            <td></td>
            <td colspan="3">Rasenplatz, Waldallee 70, 71686 Remseck am Neckar</td>
            <td></td>
          </tr>
        </tbody>
      </table>
    `;

    const games = parseClubMatchplanHtml(html);
    expect(games).toHaveLength(1);
    expect(games[0]).toEqual(expect.objectContaining({
      venueId: 'rasenplatz-waldallee-70-71686-remseck-am-neckar',
      venueName: 'Rasenplatz, Waldallee 70, 71686 Remseck am Neckar',
      date: '10.05.2026',
      time: '15:00',
      homeTeam: 'SKV Hochberg',
      guestTeam: 'VfB Neckarrems 1913 e.V.',
      competition: 'Herren | Kreisliga A; Kreisliga',
    }));
    expect(new Date(games[0].startDate).toString()).not.toBe('Invalid Date');
  });
});

describe('GET /api/club-matchplan', () => {
  it('returns 400 when id is missing', async () => {
    const res = await request(app).get('/api/club-matchplan?dateFrom=2026-05-01&dateTo=2026-05-31');
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns parsed games from the remote matchplan html', async () => {
    const html = `
      <table class="table table-striped table-full-width">
        <tbody>
          <tr class="row-competition hidden-small">
            <td class="column-date"><span class="hidden-small inline">So, 10.05.26 |&nbsp;</span>15:00</td>
            <td colspan="3" class="column-team"><a>Herren | Kreisliga A; Kreisliga</a></td>
            <td colspan="2"><a>ME | 355926184</a></td>
          </tr>
          <tr>
            <td class="hidden-small"></td>
            <td class="column-club"><a class="club-wrapper"><div class="club-name">SKV Hochberg</div></a></td>
            <td class="column-colon">:</td>
            <td class="column-club no-border"><a class="club-wrapper"><div class="club-name">VfB Neckarrems 1913 e.V.</div></a></td>
            <td class="column-score"></td>
            <td class="column-detail"></td>
          </tr>
          <tr class="row-venue hidden-small">
            <td></td>
            <td colspan="3">Rasenplatz, Waldallee 70, 71686 Remseck am Neckar</td>
            <td></td>
          </tr>
        </tbody>
      </table>
    `;
    const spy = jest.spyOn(axios, 'get').mockResolvedValue({ data: html });

    const res = await request(app)
      .get('/api/club-matchplan?id=00ES8GNAVO00000PVV0AG08LVUPGND5I&dateFrom=2026-05-01&dateTo=2026-05-31&matchType=1&max=100');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body).toHaveLength(1);
    expect(res.body[0]).toHaveProperty('venueName', 'Rasenplatz, Waldallee 70, 71686 Remseck am Neckar');
    expect(spy.mock.calls[0][0]).toContain('/match-type/1/');
  });
});

describe('PUT /api/config/club', () => {
  it('returns 400 when id is missing', async () => {
    const res = await request(app).put('/api/config/club').send({ name: 'Test' });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns 400 when id is empty string', async () => {
    const res = await request(app).put('/api/config/club').send({ id: '', name: 'Test' });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('saves club and returns ok:true with club object', async () => {
    const originalConfig = await request(app).get('/api/config');
    const originalClub = originalConfig.body.club || {};

    const res = await request(app)
      .put('/api/config/club')
      .send({ id: 'TESTCLUBID123', name: 'Test Verein' });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.club).toHaveProperty('id', 'TESTCLUBID123');
    expect(res.body.club).toHaveProperty('name', 'Test Verein');

    // Restore original club config
    if (originalClub.id) {
      await request(app)
        .put('/api/config/club')
        .send({ id: originalClub.id, name: originalClub.name || '' });
    }
  });

  it('saves club without name', async () => {
    const originalConfig = await request(app).get('/api/config');
    const originalClub = originalConfig.body.club || {};

    const res = await request(app)
      .put('/api/config/club')
      .send({ id: 'TESTCLUBID456' });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.club).toHaveProperty('id', 'TESTCLUBID456');

    // Restore original club config
    if (originalClub.id) {
      await request(app)
        .put('/api/config/club')
        .send({ id: originalClub.id, name: originalClub.name || '' });
    }
  });
});

describe('PUT /api/config/venues', () => {
  it('returns 400 when body is missing venues array', async () => {
    const res = await request(app).put('/api/config/venues').send({});
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns 400 when aliases is not an array', async () => {
    const res = await request(app)
      .put('/api/config/venues')
      .send({ venues: [{ id: 'V1', name: 'Test', aliases: 'not-an-array' }] });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('returns 400 when name_patterns is not an array', async () => {
    const res = await request(app)
      .put('/api/config/venues')
      .send({ venues: [{ id: 'V1', name: 'Test', name_patterns: 42 }] });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  it('saves venues and returns ok:true', async () => {
    const venues = [
      { id: 'V1', name: 'Platz 1', aliases: ['Alias 1'], name_patterns: ['Pattern.*1'] },
    ];
    const res = await request(app)
      .put('/api/config/venues')
      .send({ venues });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(Array.isArray(res.body.venues)).toBe(true);
    // Restore empty venues to not break other tests
    await request(app).put('/api/config/venues').send({ venues: [] });
  });
});
