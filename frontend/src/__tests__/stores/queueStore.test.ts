import { store } from '@/store';
import {
  addSource,
  cancelSync,
  fetchFeed,
  fetchSources,
  hideFeedItem,
  startResumableSync,
  useQueueStore,
} from '@/features/queue/queueStore';
import { feedItem, mockApi, mockNetworkDown, resetStores, source } from '@/test-utils';

const queue = () => store.getState().queue;
const flush = () => new Promise((r) => setImmediate(r));

beforeEach(() => resetStores());

describe('fetchFeed', () => {
  it('loads the first page, then appends the next page using the cursor', async () => {
    const api = mockApi({
      'GET /api/v1/content/feed': [
        { data: { items: [feedItem(1), feedItem(2)], next_cursor: 'c1', total_unconsumed: 3 } },
        { data: { items: [feedItem(3)], next_cursor: null, total_unconsumed: null } },
      ],
    });

    await fetchFeed(true);
    expect(queue().feedItems.map((i) => i.content_id)).toEqual(['fx:fx_vid_1', 'fx:fx_vid_2']);
    expect(queue().totalUnconsumed).toBe(3);

    await fetchFeed(false);
    expect(queue().feedItems).toHaveLength(3);
    // total_unconsumed is null on later pages (SPEC §9.2) and must not wipe the count.
    expect(queue().totalUnconsumed).toBe(3);
    expect(api.calls[1].query.cursor).toBe('c1');
  });

  it('does not request another page once the cursor is exhausted', async () => {
    const api = mockApi({
      'GET /api/v1/content/feed': { data: { items: [feedItem(1)], next_cursor: null, total_unconsumed: 1 } },
    });
    await fetchFeed(true);
    await fetchFeed(false);
    expect(api.calls).toHaveLength(1);
  });

  it('ignores a load-more while one is already in flight', async () => {
    useQueueStore.setState({ isLoadingFeed: true });
    const api = mockApi({});
    await fetchFeed(false);
    expect(api.calls).toHaveLength(0);
  });

  it('records a network failure as NETWORK_UNAVAILABLE and keeps the cached feed', async () => {
    useQueueStore.setState({ feedItems: [feedItem(1)], nextCursor: 'c1' });
    mockNetworkDown();
    await fetchFeed(true);
    expect(queue().feedError?.code).toBe('NETWORK_UNAVAILABLE');
    expect(queue().feedItems).toHaveLength(1);
    expect(queue().isRefreshingFeed).toBe(false);
  });

  it('records API errors with their code and clears them on the next success', async () => {
    mockApi({
      'GET /api/v1/content/feed': [
        { status: 503, error: { code: 'PROVIDER_UNAVAILABLE', message: 'down' } },
        { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
      ],
    });
    await fetchFeed(true);
    expect(queue().feedError).toEqual({ code: 'PROVIDER_UNAVAILABLE', message: 'down' });
    await fetchFeed(true);
    expect(queue().feedError).toBeNull();
  });
});

describe('fetchSources', () => {
  it('stores the list, and keeps the last known list on failure', async () => {
    mockApi({ 'GET /api/v1/sources': { data: { items: [source()] } } });
    await fetchSources();
    expect(queue().sources).toHaveLength(1);
    mockNetworkDown();
    await fetchSources();
    expect(queue().sources).toHaveLength(1);
  });
});

describe('addSource', () => {
  it('adds the source, records it locally, and starts a sync', async () => {
    const api = mockApi({
      'POST /api/v1/sources': { status: 201, data: source({ item_count: 3 }) },
      'POST /api/v1/sources/u1_fixture_pl/sync': {
        data: { source_id: 'u1_fixture_pl', status: 'active', items_synced: 3, has_more: false },
      },
      'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
      'GET /api/v1/sources': { data: { items: [source()] } },
    });
    const created = await addSource(' https://youtube.com/playlist?list=PL1 ');
    expect(created?.id).toBe('u1_fixture_pl');
    expect(api.calls[0].body).toEqual({ url_or_id: ' https://youtube.com/playlist?list=PL1 ' });
    expect(queue().sources?.[0].id).toBe('u1_fixture_pl');
    await flush();
    expect(api.callsTo('POST', '/api/v1/sources/u1_fixture_pl/sync')).toHaveLength(1);
  });

  it('keeps the error code so Watch Later gets its dedicated state', async () => {
    mockApi({
      'POST /api/v1/sources': {
        status: 422,
        error: { code: 'SOURCE_UNSUPPORTED', message: 'Watch Later cannot be synced' },
      },
    });
    expect(await addSource('WL')).toBeNull();
    expect(queue().addSourceErrorCode).toBe('SOURCE_UNSUPPORTED');
    expect(queue().isAddingSource).toBe(false);
    useQueueStore.getState().clearErrors();
    expect(queue().addSourceError).toBeNull();
    expect(queue().addSourceErrorCode).toBeNull();
  });
});

describe('startResumableSync', () => {
  const chunk = (n: number, hasMore: boolean) => ({
    data: { source_id: 's', status: hasMore ? 'syncing' : 'active', items_synced: n, has_more: hasMore },
  });
  const refresh = {
    'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
    'GET /api/v1/sources': { data: { items: [] } },
  };

  it('loops chunks until has_more is false and tracks progress', async () => {
    const api = mockApi({ 'POST /api/v1/sources/s/sync': [chunk(250, true), chunk(250, true), chunk(10, false)], ...refresh });
    await startResumableSync('s', 510);
    expect(api.callsTo('POST', '/api/v1/sources/s/sync')).toHaveLength(3);
    expect(queue().syncProgress).toMatchObject({ isSyncing: false, itemsSyncedTotal: 510, iterationCount: 3, error: null });
  });

  it('stops at the 40-iteration guard (SPEC §9.4) even if the server never finishes', async () => {
    const api = mockApi({ 'POST /api/v1/sources/s/sync': chunk(1, true), ...refresh });
    await startResumableSync('s');
    expect(api.callsTo('POST', '/api/v1/sources/s/sync')).toHaveLength(40);
    expect(queue().syncProgress.error).toMatch(/40/);
  });

  it('stops when cancelled between chunks', async () => {
    let calls = 0;
    mockApi({
      'POST /api/v1/sources/s/sync': () => {
        calls += 1;
        if (calls === 2) cancelSync();
        return chunk(1, true);
      },
      ...refresh,
    });
    await startResumableSync('s');
    expect(calls).toBe(2);
    expect(queue().syncProgress.error).toBe('Sync cancelled');
  });

  it('surfaces quota exhaustion with its code', async () => {
    mockApi({
      'POST /api/v1/sources/s/sync': { status: 503, error: { code: 'PROVIDER_QUOTA_EXCEEDED', message: 'quota' } },
      ...refresh,
    });
    await startResumableSync('s');
    expect(queue().syncProgress).toMatchObject({ isSyncing: false, errorCode: 'PROVIDER_QUOTA_EXCEEDED' });
  });
});

describe('hideFeedItem', () => {
  it('removes the item optimistically and calls the hide endpoint', async () => {
    useQueueStore.setState({ feedItems: [feedItem(1), feedItem(2)], totalUnconsumed: 2 });
    const api = mockApi({ 'POST /api/v1/content/feed/fx:fx_vid_1/hide': { data: { hidden: true } } });
    await hideFeedItem('fx:fx_vid_1');
    expect(queue().feedItems.map((i) => i.content_id)).toEqual(['fx:fx_vid_2']);
    expect(queue().totalUnconsumed).toBe(1);
    expect(api.calls).toHaveLength(1);
  });

  it('re-fetches the feed when the hide fails, so the item comes back', async () => {
    useQueueStore.setState({ feedItems: [feedItem(1)], totalUnconsumed: 1 });
    mockApi({
      'POST /api/v1/content/feed/fx:fx_vid_1/hide': { status: 404, error: { code: 'CONTENT_NOT_FOUND', message: 'x' } },
      'GET /api/v1/content/feed': { data: { items: [feedItem(1)], next_cursor: null, total_unconsumed: 1 } },
    });
    await hideFeedItem('fx:fx_vid_1');
    await flush();
    expect(queue().feedItems).toHaveLength(1);
  });

  it('never drives the count negative', () => {
    useQueueStore.setState({ feedItems: [feedItem(1)], totalUnconsumed: 0 });
    mockApi({ 'POST /api/v1/content/feed/fx:fx_vid_1/hide': { data: {} } });
    hideFeedItem('fx:fx_vid_1');
    expect(queue().totalUnconsumed).toBe(0);
  });
});
