import React from 'react';
import { AppState } from 'react-native';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import * as firebaseAuth from 'firebase/auth';
import { resetRouter, router } from '@/test-utils/router';
import {
  feedItem,
  mockApi,
  mockNetworkDown,
  renderWithProviders,
  resetStores,
  session,
  source,
} from '@/test-utils';
import { useQueueStore } from '@/features/queue/queueStore';
import QueueScreen from '@app/(app)/index';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

const empty = { data: { items: [], next_cursor: null, total_unconsumed: 0 } };
const noActive = { data: null };

function routes(overrides: Record<string, unknown> = {}) {
  return {
    'GET /api/v1/content/feed': { data: { items: [feedItem(1), feedItem(2)], next_cursor: 'c1', total_unconsumed: 1234 } },
    'GET /api/v1/sources': { data: { items: [source()] } },
    'GET /api/v1/sessions/active': noActive,
    ...overrides,
  } as Parameters<typeof mockApi>[0];
}

let appStateListener: ((s: string) => void) | undefined;
beforeEach(() => {
  resetStores();
  resetRouter();
  jest.spyOn(AppState, 'addEventListener').mockImplementation(((_: string, cb: (s: string) => void) => {
    appStateListener = cb;
    return { remove: jest.fn() };
  }) as never);
});

describe('QueueScreen', () => {
  it('loads feed, sources and the active session in parallel and shows the count badge', async () => {
    const api = mockApi(routes());
    await renderWithProviders(<QueueScreen />);
    expect(await screen.findByText('Fixture Workout Video #1')).toBeTruthy();
    expect(screen.getByText('1.2k')).toBeTruthy();
    expect(api.callsTo('GET', '/api/v1/sources')).toHaveLength(1);
    expect(api.callsTo('GET', '/api/v1/sessions/active')).toHaveLength(1);
  });

  it('tapping a card opens its content-first match', async () => {
    mockApi(routes());
    await renderWithProviders(<QueueScreen />);
    await fireEvent(await screen.findByTestId('feed-card-fx:fx_vid_1'), 'accessibilityAction', {
      nativeEvent: { actionName: 'activate' },
    });
    expect(router.push).toHaveBeenCalledWith({
      pathname: '/(app)/match/[contentId]',
      params: { contentId: 'fx:fx_vid_1' },
    });
  });

  it('loads the next page at the end of the list and refreshes on pull', async () => {
    const api = mockApi(routes());
    await renderWithProviders(<QueueScreen />);
    const list = await screen.findByTestId('queue-list');
    await fireEvent(list, 'endReached');
    expect(api.callsTo('GET', '/api/v1/content/feed').at(-1)?.query.cursor).toBe('c1');
    await fireEvent(list, 'refresh');
    expect(api.callsTo('GET', '/api/v1/content/feed').at(-1)?.query.cursor).toBeUndefined();
  });

  it('shows "No sources" only when the user truly has none', async () => {
    mockApi(routes({ 'GET /api/v1/content/feed': empty, 'GET /api/v1/sources': { data: { items: [] } } }));
    await renderWithProviders(<QueueScreen />);
    expect(await screen.findByText('No Content Sources Added')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Add first playlist source' }));
    expect(screen.getByText('Add Content Source')).toBeTruthy();
  });

  it('shows "All caught up" when sources exist but nothing is queued, and can re-sync', async () => {
    const api = mockApi(
      routes({
        'GET /api/v1/content/feed': empty,
        'POST /api/v1/sources/u1_fixture_pl/sync': { data: { items_synced: 0, has_more: false } },
      })
    );
    await renderWithProviders(<QueueScreen />);
    expect(await screen.findByText("You're All Caught Up!")).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Sync sources now' }));
    expect(api.callsTo('POST', '/api/v1/sources/u1_fixture_pl/sync')).toHaveLength(1);
  });

  it('shows the Offline banner when the network is down, and retries', async () => {
    mockNetworkDown();
    await renderWithProviders(<QueueScreen />);
    expect(await screen.findByText('Network Connection Offline')).toBeTruthy();
    // Not misreported as "add your first source".
    expect(screen.queryByText('No Content Sources Added')).toBeNull();
    mockApi(routes());
    await fireEvent.press(screen.getByRole('button', { name: 'Retry network connection' }));
    expect(await screen.findByText('Fixture Workout Video #1')).toBeTruthy();
    expect(screen.queryByText('Network Connection Offline')).toBeNull();
  });

  it('shows the quota banner when a source is quota-paused', async () => {
    mockApi(routes({ 'GET /api/v1/sources': { data: { items: [source({ status: 'quota_paused' })] } } }));
    await renderWithProviders(<QueueScreen />);
    expect(await screen.findByText('YouTube API Quota Reached')).toBeTruthy();
  });

  it('offers to finish a sync left mid-walk, never auto-resuming, and can dismiss it', async () => {
    const api = mockApi(
      routes({
        'GET /api/v1/sources': { data: { items: [source({ status: 'syncing', title: 'Long List' })] } },
        'POST /api/v1/sources/u1_fixture_pl/sync': { data: { items_synced: 5, has_more: false } },
      })
    );
    await renderWithProviders(<QueueScreen />);
    expect(await screen.findByText('Resume Playlist Sync')).toBeTruthy();
    expect(api.callsTo('POST', '/api/v1/sources/u1_fixture_pl/sync')).toHaveLength(0);
    await fireEvent.press(screen.getByRole('button', { name: 'Dismiss sync prompt' }));
    expect(screen.queryByText('Resume Playlist Sync')).toBeNull();
  });

  it('finishing a resumable sync calls the sync endpoint', async () => {
    const api = mockApi(
      routes({
        'GET /api/v1/sources': { data: { items: [source({ status: 'syncing', title: 'Long List' })] } },
        'POST /api/v1/sources/u1_fixture_pl/sync': { data: { items_synced: 5, has_more: false } },
      })
    );
    await renderWithProviders(<QueueScreen />);
    await fireEvent.press(await screen.findByRole('button', { name: 'Finish syncing Long List' }));
    expect(api.callsTo('POST', '/api/v1/sources/u1_fixture_pl/sync')).toHaveLength(1);
  });

  it('shows the active-session banner and resumes into the session', async () => {
    mockApi(routes({ 'GET /api/v1/sessions/active': { data: session({ status: 'in_progress' }) } }));
    await renderWithProviders(<QueueScreen />);
    await fireEvent.press(await screen.findByRole('button', { name: /Active workout session in progress/ }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/(app)/session/[id]', params: { id: 's_0001' } });
  });

  it('shows the skeleton while the first page loads', async () => {
    useQueueStore.setState({ isLoadingFeed: true });
    global.fetch = jest.fn(() => new Promise(() => undefined)) as never;
    await renderWithProviders(<QueueScreen />);
    expect(screen.getByRole('progressbar', { name: 'Loading your queue' })).toBeTruthy();
  });

  it('refetches when foregrounded after 6 hours, not before', async () => {
    const api = mockApi(routes());
    await renderWithProviders(<QueueScreen />);
    await screen.findByText('Fixture Workout Video #1');
    const before = api.callsTo('GET', '/api/v1/content/feed').length;
    await act(async () => appStateListener?.('active'));
    expect(api.callsTo('GET', '/api/v1/content/feed')).toHaveLength(before);

    const now = Date.now();
    jest.spyOn(Date, 'now').mockReturnValue(now + 7 * 3600 * 1000);
    await act(async () => appStateListener?.('active'));
    await waitFor(() => expect(api.callsTo('GET', '/api/v1/content/feed').length).toBeGreaterThan(before));
  });

  it('sign-out from the header signs out of Firebase', async () => {
    mockApi(routes());
    await renderWithProviders(<QueueScreen />);
    await fireEvent.press(screen.getByRole('button', { name: 'Sign Out' }));
    expect(firebaseAuth.signOut).toHaveBeenCalled();
  });
});
