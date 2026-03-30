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
