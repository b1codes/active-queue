import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { FeedItem, SyncProgressState } from './types';

export interface QueueState {
  feedItems: FeedItem[];
  nextCursor: string | null;
  totalUnconsumed: number | null;
  isLoadingFeed: boolean;
  isRefreshingFeed: boolean;
  syncProgress: SyncProgressState;
  addSourceError: string | null;
  isAddingSource: boolean;
}

export const INITIAL_SYNC_STATE: SyncProgressState = {
  isSyncing: false,
  sourceId: null,
  itemsSyncedTotal: 0,
  estimatedTotal: null,
  iterationCount: 0,
  isCancelled: false,
  error: null,
};

const initialState: QueueState = {
  feedItems: [],
  nextCursor: null,
  totalUnconsumed: null,
  isLoadingFeed: false,
  isRefreshingFeed: false,
  syncProgress: INITIAL_SYNC_STATE,
  addSourceError: null,
  isAddingSource: false,
};

export const queueSlice = createSlice({
  name: 'queue',
  initialState,
  reducers: {
    setQueueState: (state, action: PayloadAction<Partial<QueueState>>) => {
      Object.assign(state, action.payload);
    },
    setSyncProgress: (state, action: PayloadAction<Partial<SyncProgressState>>) => {
      Object.assign(state.syncProgress, action.payload);
    },
    cancelSync: (state) => {
      state.syncProgress.isCancelled = true;
    },
    clearErrors: (state) => {
      state.addSourceError = null;
    },
    hideFeedItemOptimistic: (state, action: PayloadAction<string>) => {
      state.feedItems = state.feedItems.filter((item) => item.content_id !== action.payload);
      if (state.totalUnconsumed !== null) {
        state.totalUnconsumed = Math.max(0, state.totalUnconsumed - 1);
      }
    },
  },
});

export const {
  setQueueState,
  setSyncProgress,
  cancelSync,
  clearErrors,
  hideFeedItemOptimistic,
} = queueSlice.actions;
