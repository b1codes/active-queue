import { create } from 'zustand';
import { apiClient } from '../../core/api/apiClient';
import { FeedItem, FeedResponse, Source, SyncChunkResponse, SyncProgressState } from './types';

interface QueueState {
  feedItems: FeedItem[];
  nextCursor: string | null;
  totalUnconsumed: number | null;
  isLoadingFeed: boolean;
  isRefreshingFeed: boolean;
  syncProgress: SyncProgressState;
  addSourceError: string | null;
  isAddingSource: boolean;

  fetchFeed: (reset?: boolean) => Promise<void>;
  addSource: (urlOrId: string) => Promise<Source | null>;
  startResumableSync: (sourceId: string, itemEstimate?: number | null) => Promise<void>;
  cancelSync: () => void;
  hideFeedItem: (contentId: string) => Promise<void>;
  clearErrors: () => void;
}

const INITIAL_SYNC_STATE: SyncProgressState = {
  isSyncing: false,
  sourceId: null,
  itemsSyncedTotal: 0,
  estimatedTotal: null,
  iterationCount: 0,
  isCancelled: false,
  error: null,
};

export const useQueueStore = create<QueueState>((set, get) => ({
  feedItems: [],
  nextCursor: null,
  totalUnconsumed: null,
  isLoadingFeed: false,
  isRefreshingFeed: false,
  syncProgress: INITIAL_SYNC_STATE,
  addSourceError: null,
  isAddingSource: false,

  fetchFeed: async (reset = false) => {
    const { nextCursor, isLoadingFeed } = get();

    if (reset) {
      set({ isRefreshingFeed: true });
    } else {
      if (isLoadingFeed || (nextCursor === null && get().feedItems.length > 0)) {
        return;
      }
      set({ isLoadingFeed: true });
    }

    try {
      const cursorParam = reset ? '' : nextCursor ? `&cursor=${encodeURIComponent(nextCursor)}` : '';
      const path = `/api/v1/content/feed?limit=20${cursorParam}`;
      const data = await apiClient<FeedResponse>(path);

      set((state) => ({
        feedItems: reset ? data.items : [...state.feedItems, ...data.items],
        nextCursor: data.next_cursor,
        totalUnconsumed:
          data.total_unconsumed !== null ? data.total_unconsumed : state.totalUnconsumed,
        isLoadingFeed: false,
        isRefreshingFeed: false,
      }));
    } catch {
      set({ isLoadingFeed: false, isRefreshingFeed: false });
    }
  },

  addSource: async (urlOrId: string) => {
    set({ isAddingSource: true, addSourceError: null });
    try {
      const data = await apiClient<Source>('/api/v1/sources', {
        method: 'POST',
        body: JSON.stringify({ url_or_id: urlOrId }),
      });

      set({ isAddingSource: false });

      if (data?.id) {
        get().startResumableSync(data.id, data.item_count);
      }

      return data;
    } catch (err: any) {
      const errorMsg = err?.message || 'Failed to add content source';
      set({ addSourceError: errorMsg, isAddingSource: false });
      return null;
    }
  },

  startResumableSync: async (sourceId: string, itemEstimate?: number | null) => {
    set({
      syncProgress: {
        isSyncing: true,
        sourceId,
        itemsSyncedTotal: 0,
        estimatedTotal: itemEstimate || null,
        iterationCount: 0,
        isCancelled: false,
        error: null,
      },
    });

    let currentIteration = 0;
    let hasMore = true;
    let totalSynced = 0;

    while (hasMore) {
      if (get().syncProgress.isCancelled) {
        set((state) => ({
          syncProgress: { ...state.syncProgress, isSyncing: false, error: 'Sync cancelled' },
        }));
        break;
      }

      // 40-Iteration Guardrail (SPEC §9.4): Max 40 chunks per sync session to prevent infinite quota burn
      if (currentIteration >= 40) {
        set((state) => ({
          syncProgress: {
            ...state.syncProgress,
            isSyncing: false,
            error: 'Sync iteration limit reached (40 chunks)',
          },
        }));
        break;
      }

      try {
        currentIteration += 1;

        const chunkData = await apiClient<SyncChunkResponse>(`/api/v1/sources/${sourceId}/sync`, {
          method: 'POST',
        });

        totalSynced += chunkData.items_synced;
        hasMore = chunkData.has_more;

        set((state) => ({
          syncProgress: {
            ...state.syncProgress,
            itemsSyncedTotal: totalSynced,
            iterationCount: currentIteration,
          },
        }));

        if (!hasMore) {
          set((state) => ({
            syncProgress: {
              ...state.syncProgress,
              isSyncing: false,
            },
          }));
          break;
        }
      } catch (err: any) {
        const errorMsg = err?.message || 'Sync chunk failed';
        set((state) => ({
          syncProgress: { ...state.syncProgress, isSyncing: false, error: errorMsg },
        }));
        break;
      }
    }

    // Refresh feed after sync completes
    get().fetchFeed(true);
  },

  cancelSync: () => {
    set((state) => ({
      syncProgress: { ...state.syncProgress, isCancelled: true },
    }));
  },

  hideFeedItem: async (contentId: string) => {
    // Optimistic update per SPEC §9.1 & §9.2
    set((state) => ({
      feedItems: state.feedItems.filter((item) => item.content_id !== contentId),
      totalUnconsumed:
        state.totalUnconsumed !== null ? Math.max(0, state.totalUnconsumed - 1) : null,
    }));

    try {
      await apiClient(`/api/v1/content/feed/${encodeURIComponent(contentId)}/hide`, {
        method: 'POST',
      });
    } catch {
      // Re-sync feed on error
      get().fetchFeed(true);
    }
  },

  clearErrors: () => {
    set({ addSourceError: null });
  },
}));
