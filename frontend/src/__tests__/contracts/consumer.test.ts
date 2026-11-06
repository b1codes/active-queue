/**
 * Consumer side of the API contract (contracts/interactions/, ClickUp 86bcxruxt).
 *
 * Each interaction lists the app functions that consume it. For every pair, the real app
 * code runs against a fetch that serves the recorded response envelope verbatim, and the
 * test checks that:
 *   1. the app sent exactly the contract request (method, path + query as sent on the
 *      wire, JSON body, bearer token), and
 *   2. the app handled exactly the contract response (returned data, store state, or a
 *      typed ApiError carrying the code, status, details and Retry-After).
 *
 * The backend replays the same files against the real API on the emulators, so a change
 * on either side that breaks the other fails CI. Background requests an action makes
 * after the one under test (e.g. the feed refresh after a sync) are answered from other
 * contract examples for the same operation.
 */
import fs from 'fs';
import path from 'path';
import type { User } from 'firebase/auth';
import { apiClient, ApiError } from '@/core/api/apiClient';
import * as matchingApi from '@/features/matching/matchingApi';
import * as sessionApi from '@/features/sessions/sessionApi';
import {
  addSource,
  fetchFeed,
  fetchSources,
  hideFeedItem,
  startResumableSync,
} from '@/features/queue/queueStore';
import { createNewSession } from '@/features/sessions/sessionStore';
import { setAuthState } from '@/features/auth/authSlice';
import { store } from '@/store';
import { resetStores } from '@/test-utils';

// ---- Contract files ------------------------------------------------------------------

const CONTRACTS = path.resolve(__dirname, '../../../../contracts');

interface Envelope {
  status: 'success' | 'error';
  data: unknown;
  error: { code: string; message: string; details: { field: string; issue: string }[] } | null;
}

interface Interaction {
  id: string;
  request: { method: string; path: string; auth?: string; body?: unknown };
  response: { status: number; headers?: Record<string, string>; body: Envelope };
  consumers: string[];
}

const interactions: Interaction[] = fs
  .readdirSync(path.join(CONTRACTS, 'interactions'))
  .filter((f) => f.endsWith('.json'))
  .sort()
  .flatMap(
    (f) =>
      (
        JSON.parse(fs.readFileSync(path.join(CONTRACTS, 'interactions', f), 'utf8')) as {
          interactions: Interaction[];
        }
      ).interactions
  );

const templates: RegExp[] = Object.keys(
  (JSON.parse(fs.readFileSync(path.join(CONTRACTS, 'openapi.json'), 'utf8')) as {
    paths: Record<string, unknown>;
  }).paths
).map((t) => new RegExp('^' + t.replace(/\{[^/]+\}/g, '[^/]+') + '$'));

function templateOf(pathAndQuery: string): RegExp | undefined {
  const bare = decodeURIComponent(pathAndQuery.split('?')[0]);
  // Prefer literal routes (/sessions/active) over parameterised ones (/sessions/{id}).
  return templates
    .filter((t) => t.test(bare))
    .sort((a, b) => a.source.split('[^/]+').length - b.source.split('[^/]+').length)[0];
}

// ---- Fetch that serves contract envelopes -------------------------------------------

interface WireCall {
  method: string;
  pathAndQuery: string;
  body: unknown;
  authorization: string | undefined;
}

function respond(res: Interaction['response']): Response {
  const headers = new Map(Object.entries(res.headers ?? {}));
  return {
    ok: res.status >= 200 && res.status < 300,
    status: res.status,
    headers: { get: (name: string) => headers.get(name) ?? null },
    json: async () => structuredClone(res.body),
  } as unknown as Response;
}

/** Serve `sequence` in order for the calls under test, then background calls by operation. */
function serve(sequence: Interaction['response'][]): WireCall[] {
  const calls: WireCall[] = [];
  const queue = [...sequence];
  global.fetch = jest.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    const method = (init.method ?? 'GET').toUpperCase();
    const pathAndQuery = url.pathname + url.search;
    const headers = (init.headers ?? {}) as Record<string, string>;
    calls.push({
      method,
      pathAndQuery,
      body: typeof init.body === 'string' ? JSON.parse(init.body) : undefined,
      authorization: headers['Authorization'],
    });
    const next = queue.shift();
    if (next) return respond(next);
    const template = templateOf(pathAndQuery);
    const background = interactions.find(
      (it) =>
        it.request.method === method &&
        it.response.status < 300 &&
        template !== undefined &&
        templateOf(it.request.path)?.source === template.source
    );
    if (!background) throw new Error(`no contract example for background ${method} ${pathAndQuery}`);
    return respond(background.response);
  }) as unknown as typeof fetch;
  return calls;
}

// ---- Helpers --------------------------------------------------------------------------

const data = (it: Interaction) => it.response.body.data as Record<string, unknown>;
const body = (it: Interaction) => it.request.body as Record<string, unknown>;
const idFromPath = (it: Interaction, re: RegExp) =>
  decodeURIComponent(re.exec(it.request.path.split('?')[0])![1]);
const sessionId = (it: Interaction) => idFromPath(it, /\/sessions\/([^/?]+)/);

async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  const err = await promise.then(
    () => {
      throw new Error('expected the call to reject with the contract error');
    },
    (e: unknown) => e
  );
  expect(err).toBeInstanceOf(ApiError);
  return err as ApiError;
}

function expectContractError(err: ApiError, it: Interaction): void {
  const { error } = it.response.body;
  expect(err.code).toBe(error!.code);
  expect(err.message).toBe(error!.message);
  expect(err.status).toBe(it.response.status);
  expect(err.details).toEqual(error!.details);
  const retryAfter = it.response.headers?.['Retry-After'];
  expect(err.retryAfterSeconds).toBe(retryAfter === undefined ? undefined : Number(retryAfter));
}

/** Let fire-and-forget follow-ups (sync after add, refresh after sync) settle. */
const settle = () => new Promise((r) => setTimeout(r, 0));

// ---- Consumers: app code under test, keyed by the names used in the contract files ----

type Consumer = (it: Interaction) => Promise<void>;

const consumers: Record<string, Consumer> = {
  listActivities: async (it) => {
    expect(await matchingApi.listActivities()).toEqual(data(it).activities);
  },
  listTimeBlocks: async (it) => {
    expect(await matchingApi.listTimeBlocks()).toEqual(data(it).time_blocks);
  },
  matchContent: async (it) => {
    expect(await matchingApi.matchContent(body(it).content_id as string)).toEqual(data(it));
  },
  'matchContent.error': async (it) => {
    expectContractError(await rejection(matchingApi.matchContent(body(it).content_id as string)), it);
  },
  matchTimeBlock: async (it) => {
    const target = body(it).target_duration_seconds as number;
    expect(await matchingApi.matchTimeBlock(target)).toEqual(data(it));
  },
  'matchTimeBlock.error': async (it) => {
    const target = body(it).target_duration_seconds as number;
    expectContractError(await rejection(matchingApi.matchTimeBlock(target)), it);
  },

  createSession: async (it) => {
    expect(await sessionApi.createSession(body(it) as unknown as sessionApi.CreateSessionInput)).toEqual(
      data(it)
    );
  },
  'createNewSession.conflict': async (it) => {
    expect(await createNewSession(body(it) as unknown as sessionApi.CreateSessionInput)).toBeNull();
    const { session } = store.getState();
    expect(session.errorCode).toBe(it.response.body.error!.code);
    // The conflicting session's id travels in error.details (SPEC §7.1 "Resume" offer).
    expect(session.conflictSessionId).toBe(it.response.body.error!.details[0].issue);
  },
  getActiveSession: async (it) => {
    expect(await sessionApi.getActiveSession()).toEqual(it.response.body.data);
  },
  startSession: async (it) => {
    expect(await sessionApi.startSession(sessionId(it))).toEqual(data(it));
  },
  'startSession.error': async (it) => {
    expectContractError(await rejection(sessionApi.startSession(sessionId(it))), it);
  },
  completeSession: async (it) => {
    expect(await sessionApi.completeSession(sessionId(it))).toEqual(data(it));
  },
  'completeSession.error': async (it) => {
    expectContractError(await rejection(sessionApi.completeSession(sessionId(it))), it);
  },
  abandonSession: async (it) => {
    expect(await sessionApi.abandonSession(sessionId(it))).toEqual(data(it));
  },
  discardSession: async (it) => {
    await expect(sessionApi.discardSession(sessionId(it))).resolves.toBeUndefined();
  },
  'discardSession.error': async (it) => {
    expectContractError(await rejection(sessionApi.discardSession(sessionId(it))), it);
  },
  listSessions: async (it) => {
    expect(await sessionApi.listSessions()).toEqual(data(it));
  },

  fetchFeed: async (it) => {
    await fetchFeed(true);
    const { queue } = store.getState();
    expect(queue.feedError).toBeNull();
    expect(queue.feedItems).toEqual(data(it).items);
    expect(queue.nextCursor).toEqual(data(it).next_cursor);
    expect(queue.totalUnconsumed).toEqual(data(it).total_unconsumed);
  },
  fetchSources: async (it) => {
    await fetchSources();
    expect(store.getState().queue.sources).toEqual(data(it).items);
  },
  addSource: async (it) => {
    expect(await addSource(body(it).url_or_id as string)).toEqual(data(it));
    expect(store.getState().queue.sources?.[0]).toEqual(data(it));
    await settle();
  },
  'addSource.error': async (it) => {
    expect(await addSource(body(it).url_or_id as string)).toBeNull();
    const { queue } = store.getState();
    expect(queue.addSourceErrorCode).toBe(it.response.body.error!.code);
    expect(queue.addSourceError).toBe(it.response.body.error!.message);
  },
  startResumableSync: async (it) => {
    await startResumableSync(idFromPath(it, /\/sources\/([^/]+)\/sync/));
    const progress = store.getState().queue.syncProgress;
    expect(progress.error).toBeNull();
    expect(progress.itemsSyncedTotal).toBe(data(it).items_synced);
    expect(progress.isSyncing).toBe(data(it).has_more);
    await settle();
  },
  'startResumableSync.error': async (it) => {
    await startResumableSync(idFromPath(it, /\/sources\/([^/]+)\/sync/));
    const progress = store.getState().queue.syncProgress;
    expect(progress.isSyncing).toBe(false);
    expect(progress.errorCode).toBe(it.response.body.error!.code);
    await settle();
  },
  hideFeedItem: async (it) => {
    await hideFeedItem(idFromPath(it, /\/feed\/([^/]+)\/hide/));
    // Success must not trigger the error path's feed re-sync.
    expect(jest.mocked(global.fetch)).toHaveBeenCalledTimes(1);
  },

  'apiClient.error': async (it) => {
    expectContractError(await rejection(apiClient(it.request.path)), it);
  },
};

/** Consumers that span several requests and get a dedicated test below. */
const multiRequestFlows = new Set(['apiClient.refresh']);

// ---- Tests ------------------------------------------------------------------------------

const pairs = interactions.flatMap((it) =>
  it.consumers.filter((c) => !multiRequestFlows.has(c)).map((c) => [it.id, c, it] as const)
);

beforeEach(() => {
  resetStores();
});

describe('contract consumers', () => {
  it.each(pairs)('%s via %s', async (_id, name, it) => {
    if (it.request.auth === 'none') store.dispatch(setAuthState({ idToken: null }));
    const calls = serve([it.response]);

    await consumers[name](it);

    const first = calls[0];
    expect(first).toBeDefined();
    expect(first.method).toBe(it.request.method);
    expect(first.pathAndQuery).toBe(it.request.path);
    expect(first.body).toEqual('body' in it.request ? it.request.body : undefined);
    expect(first.authorization).toBe(it.request.auth === 'none' ? undefined : 'Bearer test-token');
  });

  it('refreshes an expired token once and retries the same request', async () => {
    const expired = interactions.find((it) => it.consumers.includes('apiClient.refresh'))!;
    const retried = interactions.find(
      (it) =>
        it.request.method === expired.request.method &&
        it.request.path === expired.request.path &&
        it.response.status === 200
    )!;
    const getIdToken = jest.fn(async () => 'fresh-token');
    store.dispatch(setAuthState({ user: { getIdToken } as unknown as User }));
    const calls = serve([expired.response, retried.response]);

    const result = await apiClient(expired.request.path);

    expect(getIdToken).toHaveBeenCalledWith(true);
    expect(calls.map((c) => [c.pathAndQuery, c.authorization])).toEqual([
      [expired.request.path, 'Bearer test-token'],
      [expired.request.path, 'Bearer fresh-token'],
    ]);
    expect(result).toEqual(retried.response.body.data);
  });
});

describe('contract coverage', () => {
  it('names only consumers that exist', () => {
    const named = new Set(interactions.flatMap((it) => it.consumers));
    expect([...named].filter((n) => !(n in consumers) && !multiRequestFlows.has(n))).toEqual([]);
  });

  it('exercises every consumer at least once', () => {
    const named = new Set(interactions.flatMap((it) => it.consumers));
    const all = [...Object.keys(consumers), ...multiRequestFlows];
    expect(all.filter((n) => !named.has(n))).toEqual([]);
  });

  it('covers every exported API function', () => {
    const exported = [...Object.entries(matchingApi), ...Object.entries(sessionApi)]
      .filter(([, v]) => typeof v === 'function')
      .map(([k]) => k);
    expect(exported.filter((n) => !(n in consumers))).toEqual([]);
  });
});
