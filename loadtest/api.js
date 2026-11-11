// API load test (ClickUp 86bcxrv0j). Run it through loadtest/run.sh, which starts the stack
// and mints the tokens. See docs/testing.md#performance-and-load-tests.
//
// Scenarios:
//   journey  Each virtual user is one app user doing what the app does: open the feed,
//            match a time block, start a session, complete or abandon it, check history.
//            Budgets: p95 latency per endpoint, no 5xx, and never a 429. Legitimate use
//            must not be throttled.
//   abuser   One user requesting the feed 4 times a second (240/min against a 60/min
//            limit). Must get 429s with Retry-After, without slowing anyone else.
//   flood    One address without a token at 15 requests/s (900/min against the 300/min
//            per-IP guard). Must be cut off. Local profile only: on staging every
//            virtual user shares the generator's address, so it would throttle them all.
//
// Env: BASE_URL, TOKENS (path to tokens.json), PROFILE (local | staging | smoke),
//      SPOOF_IPS=1 to give each user its own X-Forwarded-For address (local stack only,
//      with TRUSTED_PROXY_HOPS=1, which is what Cloud Run's front end provides),
//      PLAYLIST (what each user syncs before the run).

import http from 'k6/http';
import { check, fail, sleep } from 'k6';
import { Counter } from 'k6/metrics';
import exec from 'k6/execution';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8080';
const PROFILE = __ENV.PROFILE || 'local';
const SPOOF_IPS = __ENV.SPOOF_IPS === '1';
const PLAYLIST = __ENV.PLAYLIST || 'fixture-small-playlist';
const TOKENS = JSON.parse(open(__ENV.TOKENS || './tokens.json'));
// The last token belongs to the abuser; the rest are journey users.
const JOURNEY_USERS = TOKENS.length - 1;
const TIME_BLOCKS = [900, 1200, 1800, 2700, 3600, 4500, 5400]; // SPEC §5.3

const PROFILES = {
  // Nightly, against the API on the emulators.
  local: { duration: '3m', abuser: true, flood: true },
  // Nightly, against staging. Everything shares one address and its 300/min per-IP
  // budget, so the abuser runs just over its own limit and the flood is off.
  staging: { duration: '3m', abuser: true, flood: false, abuserRate: 75 },
  // Per PR: short, and only the correctness thresholds (see `thresholds` below). The
  // limiter's windows are fixed to the minute, so a run straddling a boundary can split
  // a client's requests in two: each half (22.5 s) must still exceed its limit on its own.
  // abuser: 22.5 s x 4/s = 90 > 60; flood: 22.5 s x 15/s = 337 > 300.
  smoke: { duration: '45s', abuser: true, flood: true },
};
const P = PROFILES[PROFILE];
if (!P) fail(`unknown PROFILE ${PROFILE}`);

const legitRateLimited = new Counter('legit_rate_limited');
const serverErrors = new Counter('server_errors');
const abuserLimited = new Counter('abuser_limited');
const abuserLimitedWithoutRetryAfter = new Counter('abuser_limited_without_retry_after');
const floodLimited = new Counter('flood_limited');

// p95 budgets in ms per endpoint (the `name` tag).
//   staging: real Firestore. GET /content/feed is SPEC §1.4's 400 ms warm budget; the
//            rest are what a Cloud Run instance on indexed Firestore should comfortably
//            beat.
//   local:   the emulator stack. The emulator scans a collection for every query, so these
//            are regression budgets with about 2x headroom over a CI runner, not targets.
const LATENCY_P95 = {
  staging: {
    feed: 400,
    activities: 150,
    match_time: 400,
    match: 250,
    session_create: 500,
    session_start: 300,
    session_complete: 500,
    session_abandon: 300,
    history: 300,
    me: 250,
    sources: 250,
  },
  local: {
    feed: 800,
    activities: 100,
    match_time: 700,
    match: 100,
    session_create: 250,
    session_start: 100,
    session_complete: 100,
    session_abandon: 100,
    history: 250,
    me: 50,
    sources: 100,
  },
};

const thresholds = {
  legit_rate_limited: ['count==0'],
  server_errors: ['count==0'],
  'checks{scenario:journey}': ['rate>0.99'],
};
if (P.abuser && PROFILE !== 'staging') {
  // Staging can run more than one instance, and the limiter is per instance (SPEC §10.2),
  // so the abuser is only guaranteed to be limited on a single local instance.
  thresholds.abuser_limited = ['count>0'];
}
if (P.abuser) thresholds.abuser_limited_without_retry_after = ['count==0'];
if (P.flood) thresholds.flood_limited = ['count>0'];
// The per-PR smoke run is too short for stable percentiles, so it only trips at 10x the
// local budgets: a pathological regression, never noise.
const budgets = PROFILE === 'smoke' ? LATENCY_P95.local : LATENCY_P95[PROFILE];
const factor = PROFILE === 'smoke' ? 10 : 1;
for (const [name, p95] of Object.entries(budgets)) {
  thresholds[`http_req_duration{scenario:journey,name:${name}}`] = [`p(95)<${p95 * factor}`];
}

const scenarios = {
  journey: {
    executor: 'constant-vus',
    exec: 'journey',
    vus: JOURNEY_USERS,
    duration: P.duration,
  },
};
if (P.abuser) {
  scenarios.abuser = {
    executor: 'constant-arrival-rate',
    exec: 'abuser',
    rate: P.abuserRate || 240,
    timeUnit: '1m',
    duration: P.duration,
    preAllocatedVUs: 4,
    maxVUs: 20,
  };
}
if (P.flood) {
  scenarios.flood = {
    executor: 'constant-arrival-rate',
    exec: 'flood',
    rate: 15,
    timeUnit: '1s',
    duration: P.duration,
    preAllocatedVUs: 4,
    maxVUs: 20,
  };
}

export const options = {
  scenarios,
  thresholds,
  setupTimeout: '5m',
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

function headers(user, extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra };
  if (user !== null) h.Authorization = `Bearer ${TOKENS[user]}`;
  if (SPOOF_IPS) h['X-Forwarded-For'] = `10.20.${Math.floor((user ?? 999) / 250)}.${((user ?? 999) % 250) + 1}`;
  return h;
}

function call(user, method, path, body, name, { legit = true } = {}) {
  const res = http.request(method, `${BASE_URL}${path}`, body === undefined ? null : JSON.stringify(body), {
    headers: headers(user),
    tags: { name },
  });
  if (res.status >= 500) {
    serverErrors.add(1, { name });
    console.error(`${method} ${path} -> ${res.status} ${res.body}`);
  }
  if (legit && res.status === 429) {
    legitRateLimited.add(1, { name });
    console.error(`legitimate ${method} ${path} was rate-limited: ${res.body}`);
  }
  return res;
}

function data(res) {
  try {
    return res.json('data');
  } catch {
    return null;
  }
}

function think() {
  sleep(1 + Math.random() * 2);
}

// Each user signs in and syncs a playlist once, before the clock starts.
export function setup() {
  const health = http.get(`${BASE_URL}/health`);
  if (health.status !== 200) fail(`API not healthy at ${BASE_URL}: ${health.status}`);
  for (let user = 0; user < TOKENS.length; user++) {
    const me = call(user, 'GET', '/api/v1/users/me', undefined, 'setup');
    if (me.status !== 200) fail(`user ${user} can't sign in: ${me.status} ${me.body}`);
    const existing = data(call(user, 'GET', '/api/v1/sources', undefined, 'setup'))?.items ?? [];
    let source = existing[0]?.id;
    if (!source) {
      const added = call(user, 'POST', '/api/v1/sources', { url_or_id: PLAYLIST }, 'setup');
      if (added.status !== 201) fail(`user ${user} can't add ${PLAYLIST}: ${added.status} ${added.body}`);
      source = data(added).id;
    }
    for (let chunk = 0; chunk < 40; chunk++) {
      const res = call(user, 'POST', `/api/v1/sources/${source}/sync`, undefined, 'setup', { legit: false });
      if (res.status === 429) {
        sleep(Number(res.headers['Retry-After'] || 5));
        continue;
      }
      if (res.status !== 200) fail(`user ${user} sync failed: ${res.status} ${res.body}`);
      if (!data(res).has_more) break;
    }
  }
}

function clearActive(user) {
  const active = data(call(user, 'GET', '/api/v1/sessions/active', undefined, 'session_active'));
  if (!active) return;
  if (active.status === 'pending') call(user, 'DELETE', `/api/v1/sessions/${active.id}`, undefined, 'session_discard');
  else call(user, 'POST', `/api/v1/sessions/${active.id}/abandon`, undefined, 'session_abandon');
}

// VU IDs are shared by every scenario, so a journey VU claims its user on its first
// iteration: all journey VUs start together, so their first iterations are numbered
// 0..JOURNEY_USERS-1 in the scenario.
let myUser = null;

export function journey() {
  if (myUser === null) {
    myUser = exec.scenario.iterationInTest % JOURNEY_USERS;
    // Users open the app at different moments, not all in the same millisecond.
    sleep(Math.random() * 15);
  }
  const user = myUser;

  const feed = call(user, 'GET', '/api/v1/content/feed?limit=20', undefined, 'feed');
  check(feed, { 'feed 200': (r) => r.status === 200 });
  think();

  check(call(user, 'GET', '/api/v1/activities', undefined, 'activities'), {
    'activities 200': (r) => r.status === 200,
  });
  think();

  const block = TIME_BLOCKS[Math.floor(Math.random() * TIME_BLOCKS.length)];
  const matched = call(user, 'POST', '/api/v1/content/match-time', { target_duration_seconds: block }, 'match_time');
  check(matched, { 'match-time 200': (r) => r.status === 200 });
  const candidates = data(matched)?.matched_items ?? [];
  const items = candidates.length ? candidates : data(feed)?.items ?? [];
  think();

  let body;
  if (items.length) {
    const item = items[Math.floor(Math.random() * Math.min(items.length, 5))];
    check(call(user, 'POST', '/api/v1/content/match', { content_id: item.content_id }, 'match'), {
      'match 200': (r) => r.status === 200,
    });
    body = { activity_id: 'running', match_mode: 'content_first', content_id: item.content_id };
  } else {
    body = { activity_id: 'running', match_mode: 'time_first', target_duration_seconds: block };
  }
  think();

  let created = call(user, 'POST', '/api/v1/sessions', body, 'session_create');
  if (created.status === 409) {
    // A session left over from an earlier iteration (or a lost race) holds the slot.
    clearActive(user);
    created = call(user, 'POST', '/api/v1/sessions', body, 'session_create');
  }
  if (!check(created, { 'create 201': (r) => r.status === 201 })) return;
  const sessionId = data(created).id;
  think();

  check(call(user, 'POST', `/api/v1/sessions/${sessionId}/start`, undefined, 'session_start'), {
    'start 200': (r) => r.status === 200,
  });
  think();

  if (Math.random() < 0.75) {
    check(call(user, 'POST', `/api/v1/sessions/${sessionId}/complete`, {}, 'session_complete'), {
      'complete 200': (r) => r.status === 200,
    });
  } else {
    check(call(user, 'POST', `/api/v1/sessions/${sessionId}/abandon`, undefined, 'session_abandon'), {
      'abandon 200': (r) => r.status === 200,
    });
  }
  think();

  check(call(user, 'GET', '/api/v1/sessions?limit=20', undefined, 'history'), {
    'history 200': (r) => r.status === 200,
  });
  if (Math.random() < 0.3) {
    call(user, 'GET', '/api/v1/users/me', undefined, 'me');
    call(user, 'GET', '/api/v1/sources', undefined, 'sources');
  }
  think();
}

export function abuser() {
  const user = TOKENS.length - 1;
  const res = call(user, 'GET', '/api/v1/content/feed?limit=20', undefined, 'abuser', { legit: false });
  if (res.status === 429) {
    abuserLimited.add(1);
    if (!res.headers['Retry-After']) abuserLimitedWithoutRetryAfter.add(1);
  }
}

export function flood() {
  // No token, so it never reaches the per-user limiter; only the per-IP guard can stop it.
  const res = http.get(`${BASE_URL}/api/v1/activities`, {
    headers: SPOOF_IPS ? { 'X-Forwarded-For': '10.99.0.1' } : {},
    tags: { name: 'flood' },
  });
  if (res.status === 429) floodLimited.add(1);
  else if (res.status >= 500) serverErrors.add(1, { name: 'flood' });
}
