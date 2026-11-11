/**
 * Gesture races: what a user's thumb does faster than React re-renders.
 *
 * - Double taps land as two presses before the first press's state update disables the
 *   button, so `disabled={isLoading}` alone never stops them. Each action must be guarded
 *   where it starts, not where it renders.
 * - Back navigation mid-request: the screen unmounts while its request is in flight.
 * - Backgrounding mid-sync: iOS suspends the app, and on return the sync must still be one
 *   loop, not two.
 */
import React from 'react';
import { AppState, Linking } from 'react-native';
import { act, screen, waitFor } from '@testing-library/react-native';
import { resetRouter, router, setParams } from '@/test-utils/router';
import {
  activity,
  feedItem,
  mockApi,
  renderWithProviders,
  resetStores,
  session,
  source,
} from '@/test-utils';
import { useQueueStore } from '@/features/queue/queueStore';
import { useSessionStore } from '@/features/sessions/sessionStore';
import QueueScreen from '@app/(app)/index';
import MatchScreen from '@app/(app)/match/[contentId]';
import SessionScreen from '@app/(app)/session/[id]';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

let appStateListeners: ((s: string) => void)[] = [];

beforeEach(() => {
  resetStores();
  resetRouter();
  appStateListeners = [];
  jest.spyOn(Linking, 'canOpenURL').mockResolvedValue(true);
  jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
  jest.spyOn(AppState, 'addEventListener').mockImplementation(((_: string, cb: (s: string) => void) => {
    appStateListeners.push(cb);
    return { remove: () => (appStateListeners = appStateListeners.filter((l) => l !== cb)) };
  }) as never);
});

type Host = ReturnType<typeof screen.getByRole>;

const button = (name: string | RegExp) => screen.getByRole('button', { name });

const tapEvent = { nativeEvent: {}, stopPropagation: () => {}, persist: () => {} };

/**
 * Two presses in one frame: both reach the handler before React re-renders the button
 * disabled. The host view's onClick is Pressability's press entry point.
 */
async function doubleTap(el: Host): Promise<void> {
  const click = el.props.onClick as (e: typeof tapEvent) => void;
  await act(async () => {
    click(tapEvent);
    click(tapEvent);
  });
}

/** One press that doesn't wait for the work it starts (a gated request never would). */
async function tap(el: Host): Promise<void> {
  const click = el.props.onClick as (e: typeof tapEvent) => void;
  await act(async () => click(tapEvent));
}

/** Hold every request until `release()`; responses come from `routes` as in mockApi. */
function gatedApi(routes: Parameters<typeof mockApi>[0]) {
  const api = mockApi(routes);
  const respond = global.fetch;
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  global.fetch = jest.fn(async (...args: Parameters<typeof fetch>) => {
    await gate;
    return respond(...args);
  }) as typeof fetch;
  return { ...api, release: () => act(async () => release()) };
}

describe('double taps', () => {
  beforeEach(() => setParams({ id: 's_0001' }));

  it('Open Tracker advances one step, not past the media step', async () => {
    useSessionStore.setState({ currentSession: session({ activity_id: 'yoga' }), currentStep: 1 });
    await renderWithProviders(<SessionScreen />);
    await doubleTap(button('Open Tracker App'));
    expect(useSessionStore.getState().currentStep).toBe(2);
  });

  it('Launch Media starts the session and opens the media app once', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    const api = mockApi({
      'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress' }) },
    });
    await renderWithProviders(<SessionScreen />);
    await doubleTap(button('Launch Media and Start Workout Session'));
    expect(api.callsTo('POST', '/api/v1/sessions/s_0001/start')).toHaveLength(1);
    expect(Linking.openURL).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['Mark session complete', 'complete', { status: 'in_progress' as const }, 3],
    ['Abandon session', 'abandon', { status: 'in_progress' as const }, 3],
  ])('%s sends one request and navigates once', async (name, verb, over, step) => {
    useSessionStore.setState({ currentSession: session(over), currentStep: step as 3 });
    const api = mockApi({
      [`POST /api/v1/sessions/s_0001/${verb}`]: { data: session({ status: 'completed' }) },
    });
    await renderWithProviders(<SessionScreen />);
    await doubleTap(button(name));
    expect(api.callsTo('POST', `/api/v1/sessions/s_0001/${verb}`)).toHaveLength(1);
    expect(router.replace).toHaveBeenCalledTimes(1);
  });

  it('Discard sends one delete', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    const api = mockApi({ 'DELETE /api/v1/sessions/s_0001': { data: { id: 's_0001', deleted: true } } });
    await renderWithProviders(<SessionScreen />);
    await doubleTap(button('Discard session'));
    expect(api.callsTo('DELETE', '/api/v1/sessions/s_0001')).toHaveLength(1);
    expect(router.replace).toHaveBeenCalledTimes(1);
  });

  it('Start session creates one session', async () => {
    setParams({ contentId: 'fx:fx_vid_3' });
    const api = mockApi({
      'POST /api/v1/content/match': {
        data: {
          content_id: 'fx:fx_vid_3',
          duration_seconds: 1500,
          duration_label: '25m 0s',
          matching_activities: [activity('running')],
          is_valid: true,
          rejection_reason: null,
        },
      },
      'POST /api/v1/sessions': { status: 201, data: session({ id: 's_new' }) },
    });
    await renderWithProviders(<MatchScreen />);
    await screen.findByText(/This item runs 25m 0s/);
    await doubleTap(button('Start session'));
    expect(api.callsTo('POST', '/api/v1/sessions')).toHaveLength(1);
    expect(router.push).toHaveBeenCalledTimes(1);
  });

  it('Sync Now runs one sync loop', async () => {
    const api = mockApi({
      'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
      'GET /api/v1/sources': { data: { items: [source({ id: 'src_1' })] } },
      'GET /api/v1/sessions/active': { data: null },
      'POST /api/v1/sources/src_1/sync': { data: { items_synced: 10, has_more: false } },
    });
    await renderWithProviders(<QueueScreen />);
    await doubleTap(await screen.findByRole('button', { name: 'Sync sources now' }));
    await waitFor(() => expect(useQueueStore.getState().syncProgress.isSyncing).toBe(false));
    expect(api.callsTo('POST', '/api/v1/sources/src_1/sync')).toHaveLength(1);
  });
});

describe('back navigation mid-request', () => {
  it('leaving the checklist while Mark Complete is in flight does not navigate afterwards', async () => {
    setParams({ id: 's_0001' });
    useSessionStore.setState({ currentSession: session({ status: 'in_progress' }), currentStep: 3 });
    const api = gatedApi({
      'POST /api/v1/sessions/s_0001/complete': { data: session({ status: 'completed' }) },
    });
    const errors = jest.spyOn(console, 'error');
    const { unmount } = await renderWithProviders(<SessionScreen />);
    await tap(button('Mark session complete'));
    await unmount(); // the user swiped back
    await api.release();

    // The completion itself still lands (it is the user's record), but the app must not
    // yank them to History from wherever they went.
    expect(api.callsTo('POST', '/api/v1/sessions/s_0001/complete')).toHaveLength(1);
    expect(useSessionStore.getState().currentSession).toBeNull();
    expect(router.replace).not.toHaveBeenCalled();
    expect(errors).not.toHaveBeenCalled();
  });

  it('leaving Match while Start session is in flight does not push the checklist', async () => {
    setParams({ contentId: 'fx:fx_vid_3' });
    mockApi({
      'POST /api/v1/content/match': {
        data: {
          content_id: 'fx:fx_vid_3',
          duration_seconds: 1500,
          duration_label: '25m 0s',
          matching_activities: [activity('running')],
          is_valid: true,
          rejection_reason: null,
        },
      },
    });
    const { unmount } = await renderWithProviders(<MatchScreen />);
    await screen.findByText(/This item runs 25m 0s/);
    const api = gatedApi({ 'POST /api/v1/sessions': { status: 201, data: session({ id: 's_new' }) } });
    const errors = jest.spyOn(console, 'error');
    await tap(button('Start session'));
    await unmount();
    await api.release();

    expect(router.push).not.toHaveBeenCalled();
    expect(errors).not.toHaveBeenCalled();
  });

  it('leaving a screen whose first load is in flight logs nothing', async () => {
    setParams({ contentId: 'fx:fx_vid_3' });
    const api = gatedApi({
      'POST /api/v1/content/match': { error: { code: 'CONTENT_NOT_FOUND', message: 'gone' }, status: 404 },
    });
    const errors = jest.spyOn(console, 'error');
    const { unmount } = await renderWithProviders(<MatchScreen />);
    await unmount();
    await api.release();
    expect(errors).not.toHaveBeenCalled();
  });
});

describe('backgrounding during sync', () => {
  const routes = (sync: Parameters<typeof mockApi>[0][string]) => ({
    'GET /api/v1/content/feed': { data: { items: [feedItem(1)], next_cursor: null, total_unconsumed: 1 } },
    'GET /api/v1/sources': { data: { items: [source({ id: 'src_1' })] } },
    'GET /api/v1/sessions/active': { data: null },
    'POST /api/v1/sources/src_1/sync': sync,
  });

  it('a sync that spans background and foreground finishes as one loop', async () => {
    const api = mockApi(
      routes([
        { data: { items_synced: 50, has_more: true } },
        { data: { items_synced: 50, has_more: true } },
        { data: { items_synced: 20, has_more: false } },
      ])
    );
    await renderWithProviders(<QueueScreen />);
    await screen.findByText('Fixture Workout Video #1');
    const sync = useQueueStore.getState().startResumableSync('src_1', 120);
    await act(async () => appStateListeners.forEach((l) => l('background')));
    await act(async () => appStateListeners.forEach((l) => l('active')));
    await act(async () => sync);

    expect(api.callsTo('POST', '/api/v1/sources/src_1/sync')).toHaveLength(3);
    expect(useQueueStore.getState().syncProgress).toMatchObject({ isSyncing: false, itemsSyncedTotal: 120, error: null });
  });

  it('cancel then re-sync while the old chunk is in flight leaves one loop running', async () => {
    const api = gatedApi(
      routes([
        { data: { items_synced: 50, has_more: true } },
        { data: { items_synced: 50, has_more: true } },
        { data: { items_synced: 20, has_more: false } },
      ])
    );
    const first = useQueueStore.getState().startResumableSync('src_1', 120);
    act(() => useQueueStore.getState().cancelSync());
    const second = useQueueStore.getState().startResumableSync('src_1', 120);
    await api.release();
    await act(async () => {
      await Promise.all([first, second]);
    });

    // The cancelled loop stops after its in-flight chunk; only the new loop continues.
    expect(api.callsTo('POST', '/api/v1/sources/src_1/sync')).toHaveLength(3);
    expect(useQueueStore.getState().syncProgress).toMatchObject({ isSyncing: false, error: null });
  });
});
