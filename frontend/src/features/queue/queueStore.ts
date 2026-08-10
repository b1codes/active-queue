import { store } from '@/store';
import { useAppSelector } from '@/store/hooks';
import { apiClient } from '../../core/api/apiClient';
import { FeedItem, FeedResponse, Source, SyncChunkResponse, SyncProgressState } from './types';
import {
  setQueueState,
  setSyncProgress,
  cancelSync as cancelSyncAction,
  clearErrors as clearErrorsAction,
  hideFeedItemOptimistic,
  QueueState,
  INITIAL_SYNC_STATE,
} from './queueSlice';

export interface QueueActions {
  fetchFeed: (reset?: boolean) => Promise<void>;
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
      })
    );
  } catch {
    store.dispatch(setQueueState({ isLoadingFeed: false, isRefreshingFeed: false }));
  }
}

export async function addSource(urlOrId: string): Promise<Source | null> {
  store.dispatch(setQueueState({ isAddingSource: true, addSourceError: null }));
  try {
    const data = await apiClient<Source>('/api/v1/sources', {
      method: 'POST',
      body: JSON.stringify({ url_or_id: urlOrId }),
    });

    store.dispatch(setQueueState({ isAddingSource: false }));

    if (data?.id) {
      startResumableSync(data.id, data.item_count);
    }

    return data;
  } catch (err: any) {
    const errorMsg = err?.message || 'Failed to add content source';
    store.dispatch(setQueueState({ addSourceError: errorMsg, isAddingSource: false }));
    return null;
  }
}

export async function startResumableSync(
  sourceId: string,
  itemEstimate?: number | null
): Promise<void> {
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
      },
    })
  );

  let currentIteration = 0;
  let hasMore = true;
  let totalSynced = 0;

  while (hasMore) {
    if (store.getState().queue.syncProgress.isCancelled) {
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

      totalSynced += chunkData.items_synced;
      hasMore = chunkData.has_more;

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
    } catch (err: any) {
      const errorMsg = err?.message || 'Sync chunk failed';
      store.dispatch(setSyncProgress({ isSyncing: false, error: errorMsg }));
      break;
    }
  }

  // Refresh feed after sync completes
  fetchFeed(true);
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
