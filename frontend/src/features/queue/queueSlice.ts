import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { FeedItem, Source, SyncProgressState } from './types';

export interface QueueError {
  code: string;
  message: string;
}

export interface QueueState {
  feedItems: FeedItem[];
  /** null until the first successful GET /sources; [] means the user has none. */
  sources: Source[] | null;
  /** Last feed load failure (cleared by the next success). Drives Offline/error UI. */
  feedError: QueueError | null;
  nextCursor: string | null;
  totalUnconsumed: number | null;
  isLoadingFeed: boolean;
  isRefreshingFeed: boolean;
  syncProgress: SyncProgressState;
  addSourceError: string | null;
  addSourceErrorCode: string | null;
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
  errorCode: null,
};

const initialState: QueueState = {
  feedItems: [],
  sources: null,
  feedError: null,
  nextCursor: null,
  totalUnconsumed: null,
  isLoadingFeed: false,
  isRefreshingFeed: false,
  syncProgress: INITIAL_SYNC_STATE,
  addSourceError: null,
  addSourceErrorCode: null,
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
      state.addSourceErrorCode = null;
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
