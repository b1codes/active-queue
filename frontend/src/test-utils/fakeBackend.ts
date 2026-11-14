/**
 * A stateful in-memory API for monkey runs: sessions move through the SPEC §7.1 state
 * machine, sources sync in chunks, hidden and consumed items leave the feed, and the
 * errors are the ones the real API returns (contracts/openapi.json, SPEC §9.7).
 *
 * Unlike `mockApi`, a random walk can do anything in any order here and get an answer
 * the real server would give. With `failureRate`, a seeded share of requests fail instead
 * (network down, 429, 500, 503) so error and retry paths get walked too.
 */
import type { FeedItem, Source } from '@/features/queue/types';
import type { Session } from '@/features/sessions/sessionApi';
import { activity, feedItem, source as sourceFixture, TIME_BLOCKS } from './fixtures';

export type Rng = () => number;

/** Small, fast, seedable PRNG (mulberry32). The same seed gives the same sequence. */
export function seededRng(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const ACTIVITIES = [
  activity('running', 300, 14400, 'Running'),
  activity('yoga', 600, 5400, 'Yoga'),
  activity('strength', 900, 3600, 'Strength'),
];

interface Reply {
  status: number;
  data?: unknown;
  error?: { code: string; message: string; details?: { field: string; issue: string }[] };
}

const ok = (data: unknown, status = 200): Reply => ({ status, data });
const fail = (status: number, code: string, details: { field: string; issue: string }[] = []): Reply => ({
  status,
  error: { code, message: code.toLowerCase().replace(/_/g, ' '), details },
});

const CHAOS: Reply[] = [
  fail(429, 'RATE_LIMITED'),
  fail(500, 'INTERNAL_ERROR'),
  fail(503, 'PROVIDER_UNAVAILABLE'),
  fail(503, 'PROVIDER_QUOTA_EXCEEDED'),
];

export interface FakeBackendOptions {
  rng: Rng;
  /** Share of requests (0..1) that fail with a network error or a 429/5xx. */
  failureRate?: number;
  feedSize?: number;
}

export function installFakeBackend({ rng, failureRate = 0, feedSize = 30 }: FakeBackendOptions) {
  const feed: FeedItem[] = Array.from({ length: feedSize }, (_, i) =>
    feedItem(i + 1, { source_id: 'src_1', duration_seconds: 600 + Math.floor(rng() * 12) * 300 })
  );
  const removed = new Set<string>();
  const sources: Source[] = [sourceFixture({ id: 'src_1' })];
  const chunksLeft = new Map<string, number>();
  const sessions = new Map<string, Session>();
  let nextId = 1;
  const now = () => '2026-01-01T10:00:00Z';
  const calls: string[] = [];
  const unknownRoutes: string[] = [];

  const visible = () => feed.filter((f) => !removed.has(f.content_id));
  const active = () => [...sessions.values()].find((s) => s.status === 'pending' || s.status === 'in_progress');
  const label = (s: number) => `${Math.floor(s / 60)}m ${s % 60}s`;

  function route(method: string, path: string, query: URLSearchParams, body: Record<string, unknown>): Reply {
    let m: RegExpMatchArray | null;
    const key = `${method} ${path}`;

    if (key === 'GET /api/v1/content/feed') {
      const items = visible();
      const start = Number(query.get('cursor') ?? 0) || 0;
      const limit = Number(query.get('limit') ?? 20);
      const page = items.slice(start, start + limit);
      const next = start + limit < items.length ? String(start + limit) : null;
      return ok({ items: page, next_cursor: next, total_unconsumed: items.length });
    }
    if ((m = key.match(/^POST \/api\/v1\/content\/feed\/(.+)\/hide$/))) {
      const id = m[1];
      if (!feed.some((f) => f.content_id === id)) return fail(404, 'CONTENT_NOT_FOUND');
      removed.add(id);
      return ok({ content_id: id, hidden: true });
    }
    if (key === 'POST /api/v1/content/match') {
      const item = feed.find((f) => f.content_id === body.content_id && !removed.has(f.content_id));
      if (!item) return fail(404, 'CONTENT_NOT_FOUND');
      const fits = ACTIVITIES.filter(
        (a) => item.duration_seconds >= a.min_duration_seconds && item.duration_seconds <= a.max_duration_seconds
      );
      return ok({
        content_id: item.content_id,
        duration_seconds: item.duration_seconds,
        duration_label: label(item.duration_seconds),
        matching_activities: fits,
        is_valid: fits.length > 0,
        rejection_reason: fits.length ? null : 'no_matching_activity',
      });
    }
    if (key === 'POST /api/v1/content/match-time') {
      const target = Number(body.target_duration_seconds);
      const matched = visible().filter((f) => Math.abs(f.duration_seconds - target) <= target * 0.1);
      return ok({
        target_duration_seconds: target,
        target_duration_label: label(target),
        matched_items: matched.slice(0, 5),
        window_type: matched.length ? 'primary' : null,
        is_valid: matched.length > 0,
        rejection_reason: matched.length ? null : 'no_content_in_window',
      });
    }
    if (key === 'GET /api/v1/activities') return ok({ activities: ACTIVITIES });
    if (key === 'GET /api/v1/activities/time-blocks') return ok({ time_blocks: TIME_BLOCKS });

    if (key === 'GET /api/v1/sources') return ok({ items: sources });
    if (key === 'POST /api/v1/sources') {
      const raw = String(body.url_or_id ?? '').trim();
      if (!/^(PL|UU|https?:\/\/)/.test(raw)) return fail(422, 'SOURCE_URL_UNPARSEABLE');
      if (sources.some((s) => s.external_source_id === raw)) return fail(409, 'SOURCE_ALREADY_ADDED');
      const created = sourceFixture({ id: `src_${++nextId}`, external_source_id: raw, status: 'syncing' });
      sources.unshift(created);
      return ok(created, 201);
    }
    if ((m = key.match(/^DELETE \/api\/v1\/sources\/(.+)$/))) {
      const i = sources.findIndex((s) => s.id === m![1]);
      if (i < 0) return fail(404, 'SOURCE_NOT_FOUND');
      sources.splice(i, 1);
      return ok({ source_id: m[1], deleted: true });
    }
    if ((m = key.match(/^POST \/api\/v1\/sources\/(.+)\/sync$/))) {
      const src = sources.find((s) => s.id === m![1]);
      if (!src) return fail(404, 'SOURCE_NOT_FOUND');
      const left = (chunksLeft.get(src.id) ?? 3) - 1;
      chunksLeft.set(src.id, left);
      src.status = left > 0 ? 'syncing' : 'active';
      return ok({
        source_id: src.id,
        status: src.status,
        items_synced: 10,
        has_more: left > 0,
        next_page_token: left > 0 ? `p${left}` : null,
        message: null,
      });
    }

    if (key === 'GET /api/v1/sessions/active') return ok(active() ?? null);
    if (key === 'GET /api/v1/sessions') {
      const status = query.get('status');
      const items = [...sessions.values()].filter((s) => !status || s.status === status).reverse();
      return ok({ items, next_cursor: null });
    }
    if (key === 'POST /api/v1/sessions') {
      const current = active();
      if (current) {
        return fail(409, 'ACTIVE_SESSION_EXISTS', [{ field: 'active_session_id', issue: current.id }]);
      }
      const item = feed.find((f) => f.content_id === body.content_id);
      if (body.content_id && !item) return fail(404, 'CONTENT_NOT_FOUND');
      if (!ACTIVITIES.some((a) => a.id === body.activity_id)) return fail(404, 'ACTIVITY_NOT_FOUND');
      const created: Session = {
        id: `s_${++nextId}`,
        user_id: 'u1',
        activity_id: String(body.activity_id),
        match_mode: body.match_mode as Session['match_mode'],
        content_id: (body.content_id as string | null) ?? null,
        duration_seconds: item?.duration_seconds ?? Number(body.target_duration_seconds ?? 1800),
        status: 'pending',
        checklist_completed: false,
        started_at: null,
        completed_at: null,
        abandoned_at: null,
        created_at: now(),
        updated_at: now(),
      };
      sessions.set(created.id, created);
      return ok(created, 201);
    }
    if ((m = key.match(/^(POST|DELETE) \/api\/v1\/sessions\/([^/]+)(?:\/(start|complete|abandon))?$/))) {
      const s = sessions.get(m[2]);
      if (!s) return fail(404, 'SESSION_NOT_FOUND');
      const verb = m[1] === 'DELETE' ? 'delete' : m[3];
      const terminal = s.status === 'completed' || s.status === 'abandoned';
      if (verb === 'start') {
        if (terminal) return fail(409, 'SESSION_ALREADY_TERMINAL');
        Object.assign(s, { status: 'in_progress', started_at: s.started_at ?? now(), checklist_completed: true });
        return ok(s);
      }
      if (verb === 'complete') {
        if (s.status === 'completed') return ok(s); // idempotent
        if (s.status === 'pending') return fail(409, 'SESSION_NOT_STARTED');
        if (terminal) return fail(409, 'SESSION_ALREADY_TERMINAL');
        Object.assign(s, { status: 'completed', completed_at: now() });
        if (s.content_id) removed.add(s.content_id);
        return ok(s);
      }
      if (verb === 'abandon') {
        if (s.status === 'abandoned') return ok(s);
        if (terminal) return fail(409, 'SESSION_ALREADY_TERMINAL');
        Object.assign(s, { status: 'abandoned', abandoned_at: now() });
        return ok(s);
      }
      if (verb === 'delete') {
        if (s.status !== 'pending') return fail(409, 'SESSION_ALREADY_STARTED');
        sessions.delete(s.id);
        return ok({ session_id: s.id, discarded: true });
      }
    }

    unknownRoutes.push(key);
    return fail(404, 'NOT_FOUND');
  }

  const fetchFake = jest.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    const method = (init.method ?? 'GET').toUpperCase();
    const path = decodeURIComponent(url.pathname);
    calls.push(`${method} ${path}`);
    const body = typeof init.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : {};

    let reply: Reply;
    if (failureRate > 0 && rng() < failureRate) {
      if (rng() < 0.3) throw new TypeError('Network request failed');
      reply = CHAOS[Math.floor(rng() * CHAOS.length)];
    } else {
      reply = route(method, path, url.searchParams, body);
    }
    const envelope = reply.error
      ? { status: 'error', data: null, error: { details: [], ...reply.error } }
      : { status: 'success', data: reply.data ?? null, error: null };
    return {
      ok: reply.status >= 200 && reply.status < 300,
      status: reply.status,
      headers: { get: () => null },
      // A fresh copy, as off the wire: the app's store freezes what it is given, and the
      // fake keeps mutating its own records.
      json: async () => JSON.parse(JSON.stringify(envelope)),
    } as unknown as Response;
  });

  global.fetch = fetchFake as unknown as typeof fetch;
  return { calls, unknownRoutes, sessions, sources, feed };
}
