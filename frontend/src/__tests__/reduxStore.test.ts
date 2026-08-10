import { store } from '../store';
import { authSlice, setAuthState, clearError } from '../features/auth/authSlice';
import { queueSlice, setQueueState, setSyncProgress, cancelSync, hideFeedItemOptimistic } from '../features/queue/queueSlice';
import { sessionSlice, setSessionFromServer, skipTrackerStep, advanceStep, clearSession } from '../features/sessions/sessionSlice';

describe('Redux Store & Slices', () => {
  describe('Auth Slice', () => {
    it('handles initial auth state', () => {
      const state = store.getState().auth;
      expect(state.user).toBeNull();
      expect(state.idToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(true);
      expect(state.error).toBeNull();
    });

    it('updates auth state via setAuthState reducer', () => {
      store.dispatch(
        setAuthState({
          idToken: 'mock-token-abc',
          isAuthenticated: true,
          isLoading: false,
          error: 'Some error',
        })
      );
      const state = store.getState().auth;
      expect(state.idToken).toBe('mock-token-abc');
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBe('Some error');
    });

    it('clears error via clearError reducer', () => {
      store.dispatch(clearError());
      expect(store.getState().auth.error).toBeNull();
    });
  });

  describe('Queue Slice', () => {
    it('updates queue state and handles optimistic hide', () => {
      store.dispatch(
        setQueueState({
          feedItems: [
            {
              id: '1',
              content_id: 'c1',
              source_id: 'src1',
              title: 'Video 1',
              provider: 'youtube',
              external_id: 'ext1',
              duration_seconds: 60,
              duration_label: '1m',
              published_at: '2026-08-10T00:00:00Z',
              thumbnail_url: null,
              video_url: null,
              consumed: false,
            },
            {
              id: '2',
              content_id: 'c2',
              source_id: 'src2',
              title: 'Video 2',
              provider: 'spotify',
              external_id: 'ext2',
              duration_seconds: 120,
              duration_label: '2m',
              published_at: '2026-08-10T00:00:00Z',
              thumbnail_url: null,
              video_url: null,
              consumed: false,
            },
          ],
          totalUnconsumed: 2,
        })
      );

      expect(store.getState().queue.feedItems).toHaveLength(2);
      expect(store.getState().queue.totalUnconsumed).toBe(2);

      store.dispatch(hideFeedItemOptimistic('c1'));
      expect(store.getState().queue.feedItems).toHaveLength(1);
      expect(store.getState().queue.feedItems[0].content_id).toBe('c2');
      expect(store.getState().queue.totalUnconsumed).toBe(1);
    });

    it('updates sync progress and cancels sync', () => {
      store.dispatch(setSyncProgress({ isSyncing: true, itemsSyncedTotal: 50 }));
      expect(store.getState().queue.syncProgress.isSyncing).toBe(true);
      expect(store.getState().queue.syncProgress.itemsSyncedTotal).toBe(50);

      store.dispatch(cancelSync());
      expect(store.getState().queue.syncProgress.isCancelled).toBe(true);
    });
  });

  describe('Session Slice', () => {
    it('derives step 3 for in_progress sessions when setSessionFromServer is dispatched', () => {
      store.dispatch(
        setSessionFromServer({
          id: 's1',
          user_id: 'u1',
          activity_id: 'running',
          match_mode: 'content_first',
          duration_seconds: 1800,
          status: 'in_progress',
          checklist_completed: true,
          created_at: '2026-08-10T00:00:00Z',
          updated_at: '2026-08-10T00:00:00Z',
        })
      );

      const state = store.getState().session;
      expect(state.currentSession?.id).toBe('s1');
      expect(state.currentStep).toBe(3);
    });

    it('handles step navigation and clearSession', () => {
      store.dispatch(clearSession());
      expect(store.getState().session.currentStep).toBe(1);

      store.dispatch(skipTrackerStep());
      expect(store.getState().session.currentStep).toBe(2);

      store.dispatch(advanceStep());
      expect(store.getState().session.currentStep).toBe(3);

      // Should capped at step 3
      store.dispatch(advanceStep());
      expect(store.getState().session.currentStep).toBe(3);

      store.dispatch(clearSession());
      expect(store.getState().session.currentSession).toBeNull();
      expect(store.getState().session.currentStep).toBe(1);
    });
  });
});
