import { store } from '@/store';
import { useAppSelector } from '@/store/hooks';
import { apiClient, ApiError } from '../../core/api/apiClient';
import { FeedResponse, Source, SyncChunkResponse } from './types';
import {
  setQueueState,
  setSyncProgress,
  cancelSync as cancelSyncAction,
  clearErrors as clearErrorsAction,
  hideFeedItemOptimistic,
  QueueState,
} from './queueSlice';

export interface QueueActions {
  fetchFeed: (reset?: boolean) => Promise<void>;
  fetchSources: () => Promise<void>;
  addSource: (urlOrId: string) => Promise<Source | null>;
  startResumableSync: (sourceId: string, itemEstimate?: number | null) => Promise<void>;
  cancelSync: () => void;
  hideFeedItem: (contentId: string) => Promise<void>;
  clearErrors: () => void;
}

export async function fetchFeed(reset = false): Promise<void> {
  const { nextCursor, isLoadingFeed, feedItems } = store.getState().queue;

  if (reset) {
    store.dispatch(setQueueState({ isRefreshingFeed: true }));
  } else {
    if (isLoadingFeed || (nextCursor === null && feedItems.length > 0)) {
      return;
    }
    store.dispatch(setQueueState({ isLoadingFeed: true }));
  }

  try {
    const cursorParam = reset ? '' : nextCursor ? `&cursor=${encodeURIComponent(nextCursor)}` : '';
    const path = `/api/v1/content/feed?limit=20${cursorParam}`;
    const data = await apiClient<FeedResponse>(path);

    const currentItems = store.getState().queue.feedItems;
    const currentUnconsumed = store.getState().queue.totalUnconsumed;

    store.dispatch(
      setQueueState({
        feedItems: reset ? data.items : [...currentItems, ...data.items],
        nextCursor: data.next_cursor,
        totalUnconsumed: data.total_unconsumed !== null ? data.total_unconsumed : currentUnconsumed,
        isLoadingFeed: false,
        isRefreshingFeed: false,
        feedError: null,
      })
    );
  } catch (err: unknown) {
    // Keep whatever is already loaded (the cached feed stays browsable per SPEC §11.3)
    // but record why the refresh failed so the screen can say so.
    store.dispatch(
      setQueueState({
        isLoadingFeed: false,
        isRefreshingFeed: false,
        feedError: toQueueError(err, 'Failed to load your queue'),
      })
    );
  }
}

/** GET /sources: tells "no sources yet" apart from "sources, but nothing queued". */
export async function fetchSources(): Promise<void> {
  try {
    const data = await apiClient<{ items: Source[] }>('/api/v1/sources');
    store.dispatch(setQueueState({ sources: data.items }));
  } catch {
    // Leave the last known list; feedError already reflects connectivity.
  }
}

function toQueueError(err: unknown, fallback: string): { code: string; message: string } {
  if (err instanceof ApiError) return { code: err.code, message: err.message };
  return { code: 'UNKNOWN_ERROR', message: err instanceof Error ? err.message : fallback };
}

export async function addSource(urlOrId: string): Promise<Source | null> {
  store.dispatch(
    setQueueState({ isAddingSource: true, addSourceError: null, addSourceErrorCode: null })
  );
  try {
    const data = await apiClient<Source>('/api/v1/sources', {
      method: 'POST',
      body: JSON.stringify({ url_or_id: urlOrId }),
    });

    const known = store.getState().queue.sources ?? [];
    store.dispatch(setQueueState({ isAddingSource: false, sources: [data, ...known] }));

    if (data?.id) {
      startResumableSync(data.id, data.item_count);
    }

    return data;
  } catch (err: unknown) {
    const { code, message } = toQueueError(err, 'Failed to add content source');
    store.dispatch(
      setQueueState({ addSourceError: message, addSourceErrorCode: code, isAddingSource: false })
    );
    return null;
  }
}

// Each sync loop's ticket. Starting a sync takes a new one, and a loop whose ticket is no
// longer current stops at its next check without touching syncProgress, so a cancelled or
// replaced loop can't keep calling /sync or overwrite the new loop's progress.
let currentSyncRun = 0;

// The API allows 10 sync calls a minute per user (SPEC §10.2) and a 5,000-item playlist
// takes 20 chunks, so a long sync is expected to be told to wait. It waits out the
// server's Retry-After (a fixed window, so at most a minute) this many times in a row.
const MAX_RATE_LIMIT_WAITS = 3;
const MAX_RETRY_AFTER_SECONDS = 60;

/** Resolves after `seconds`, or as soon as `stop()` is true (checked every 250 ms). */
function waitUnless(seconds: number, stop: () => boolean): Promise<void> {
  const until = Date.now() + seconds * 1000;
  return new Promise((resolve) => {
    const tick = () => {
      if (stop() || Date.now() >= until) resolve();
      else setTimeout(tick, Math.min(250, until - Date.now()));
    };
    tick();
  });
}

export async function startResumableSync(
  sourceId: string,
  itemEstimate?: number | null
): Promise<void> {
  const running = store.getState().queue.syncProgress;
  // A second tap on Sync / Finish Sync for the source already syncing is a no-op.
  if (running.isSyncing && !running.isCancelled && running.sourceId === sourceId) return;
  const run = ++currentSyncRun;
  const superseded = () => run !== currentSyncRun;

  store.dispatch(
    setQueueState({
      syncProgress: {
        isSyncing: true,
        sourceId,
        itemsSyncedTotal: 0,
        estimatedTotal: itemEstimate || null,
        iterationCount: 0,
        isCancelled: false,
        error: null,
        errorCode: null,
      },
    })
  );

  let currentIteration = 0;
  let hasMore = true;
  let totalSynced = 0;
  let rateLimitWaits = 0;
  const cancelled = () => store.getState().queue.syncProgress.isCancelled;

  while (hasMore) {
    if (superseded()) return;
    if (cancelled()) {
      store.dispatch(setSyncProgress({ isSyncing: false, error: 'Sync cancelled' }));
      break;
    }

    // 40-Iteration Guardrail (SPEC §9.4): Max 40 chunks per sync session to prevent infinite quota burn
    if (currentIteration >= 40) {
      store.dispatch(
        setSyncProgress({
          isSyncing: false,
          error: 'Sync iteration limit reached (40 chunks)',
        })
      );
      break;
    }

    try {
      currentIteration += 1;

      const chunkData = await apiClient<SyncChunkResponse>(`/api/v1/sources/${sourceId}/sync`, {
        method: 'POST',
      });
      if (superseded()) return;

      totalSynced += chunkData.items_synced;
      hasMore = chunkData.has_more;
      rateLimitWaits = 0;

      store.dispatch(
        setSyncProgress({
          itemsSyncedTotal: totalSynced,
          iterationCount: currentIteration,
        })
      );

      if (!hasMore) {
        store.dispatch(setSyncProgress({ isSyncing: false }));
        break;
      }
    } catch (err: unknown) {
      if (superseded()) return;
      const retryAfter = err instanceof ApiError && err.isRateLimited ? err.retryAfterSeconds : undefined;
      if (retryAfter !== undefined && rateLimitWaits < MAX_RATE_LIMIT_WAITS) {
        // The refused request synced nothing, so it doesn't count toward the 40-chunk guard.
        rateLimitWaits += 1;
        currentIteration -= 1;
        await waitUnless(Math.min(retryAfter, MAX_RETRY_AFTER_SECONDS), () => superseded() || cancelled());
        continue;
      }
      const { code, message } = toQueueError(err, 'Sync chunk failed');
      store.dispatch(setSyncProgress({ isSyncing: false, error: message, errorCode: code }));
      break;
    }
  }

  // Refresh feed (and source statuses) after sync completes
  fetchFeed(true);
  fetchSources();
}

export function cancelSync(): void {
  store.dispatch(cancelSyncAction());
}

export async function hideFeedItem(contentId: string): Promise<void> {
  // Optimistic update per SPEC §9.1 & §9.2
  store.dispatch(hideFeedItemOptimistic(contentId));

  try {
    await apiClient(`/api/v1/content/feed/${encodeURIComponent(contentId)}/hide`, {
      method: 'POST',
    });
  } catch {
    // Re-sync feed on error
    fetchFeed(true);
  }
}

export function clearErrors(): void {
  store.dispatch(clearErrorsAction());
}

const actions: QueueActions = {
  fetchFeed,
  fetchSources,
  addSource,
  startResumableSync,
  cancelSync,
  hideFeedItem,
  clearErrors,
};

export function useQueueStore<T = QueueState & QueueActions>(
  selector?: (state: QueueState & QueueActions) => T
): T {
  const queueState = useAppSelector((state) => state.queue);
  const combined = { ...queueState, ...actions };

  if (selector) {
    return selector(combined as QueueState & QueueActions);
  }

  return combined as unknown as T;
}

useQueueStore.getState = (): QueueState & QueueActions => {
  return {
    ...store.getState().queue,
    ...actions,
  };
};

useQueueStore.setState = (partialState: Partial<QueueState>): void => {
  store.dispatch(setQueueState(partialState));
};
