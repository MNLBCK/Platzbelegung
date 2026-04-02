'use strict';

const request = require('supertest');
const { app, server } = require('../server');

afterAll(() => server.close());

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
