import { useQueueStore } from '../features/queue/queueStore';
import { apiClient } from '../core/api/apiClient';

jest.mock('../core/api/apiClient');
const mockApiClient = apiClient as jest.MockedFunction<typeof apiClient>;

describe('useQueueStore & Sync Loop Driver', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useQueueStore.setState({
      feedItems: [],
      nextCursor: null,
      totalUnconsumed: null,
      isLoadingFeed: false,
      isRefreshingFeed: false,
      syncProgress: {
        isSyncing: false,
        sourceId: null,
        itemsSyncedTotal: 0,
        estimatedTotal: null,
        iterationCount: 0,
        isCancelled: false,
        error: null,
      },
      addSourceError: null,
      isAddingSource: false,
    });
  });

  it('startResumableSync loops until has_more is false', async () => {
    mockApiClient
      .mockResolvedValueOnce({
        source_id: 'src1',
        status: 'syncing',
        items_synced: 250,
        has_more: true,
        next_page_token: '250',
        message: null,
      } as any)
      .mockResolvedValueOnce({
        source_id: 'src1',
        status: 'active',
        items_synced: 100,
        has_more: false,
        next_page_token: null,
        message: null,
      } as any)
      .mockResolvedValueOnce({
        items: [],
        next_cursor: null,
        total_unconsumed: 350,
      } as any);

    const store = useQueueStore.getState();
    await store.startResumableSync('src1', 350);

    const state = useQueueStore.getState();
    expect(mockApiClient).toHaveBeenCalled();
    expect(state.syncProgress.itemsSyncedTotal).toBe(350);
    expect(state.syncProgress.isSyncing).toBe(false);
  });

  it('enforces 40-iteration guardrail to prevent infinite quota burn per SPEC §9.4', async () => {
    // Mock API continuously returning has_more = true
    mockApiClient.mockResolvedValue({
      source_id: 'src_bug',
      status: 'syncing',
      items_synced: 250,
      has_more: true,
      next_page_token: 'token',
      message: null,
    } as any);

    const store = useQueueStore.getState();
    await store.startResumableSync('src_bug', 10000);

    const state = useQueueStore.getState();
    // Must stop exactly at 40 iterations
    expect(state.syncProgress.iterationCount).toBe(40);
    expect(state.syncProgress.isSyncing).toBe(false);
    expect(state.syncProgress.error).toContain('40 chunks');
  });

  it('cancelSync halts sync loop immediately', async () => {
    mockApiClient.mockImplementation(async () => {
      // Simulate user tapping cancel during first chunk
      useQueueStore.getState().cancelSync();
      return {
        source_id: 'src1',
        status: 'syncing',
        items_synced: 250,
        has_more: true,
        next_page_token: '250',
        message: null,
      } as any;
    });

    const store = useQueueStore.getState();
    await store.startResumableSync('src1', 1000);

    const state = useQueueStore.getState();
    expect(state.syncProgress.isSyncing).toBe(false);
    expect(state.syncProgress.error).toBe('Sync cancelled');
  });
});
