/**
 * Runs the accessibility audit over every route in app/, in the states a user actually
 * reaches: loaded, empty, error, mid-request, and each step of the session checklist.
 */
import React from 'react';
import { AppState, Linking } from 'react-native';
import { act, fireEvent, screen } from '@testing-library/react-native';
import { resetRouter, setParams } from '@/test-utils/router';
import {
  activity,
  feedItem,
  mockApi,
  mockNetworkDown,
  renderWithProviders,
  resetStores,
  session,
  source,
  TIME_BLOCKS,
} from '@/test-utils';
import { expectAccessible } from '@/test-utils/a11y';
import { useQueueStore } from '@/features/queue/queueStore';
import { useSessionStore } from '@/features/sessions/sessionStore';
import QueueScreen from '@app/(app)/index';
import BlocksScreen from '@app/(app)/blocks';
import HistoryScreen from '@app/(app)/history';
import MatchScreen from '@app/(app)/match/[contentId]';
import SessionScreen from '@app/(app)/session/[id]';
import SettingsScreen from '@app/(app)/settings';
import SignInScreen from '@app/(auth)/sign-in';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

type Routes = Parameters<typeof mockApi>[0];

beforeEach(() => {
  resetStores();
  resetRouter();
  jest.spyOn(AppState, 'addEventListener').mockImplementation((() => ({ remove: jest.fn() })) as never);
  jest.spyOn(Linking, 'canOpenURL').mockResolvedValue(true);
  jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
});

async function audit(ui: React.ReactElement, routes: Routes | 'offline', ready: () => Promise<unknown>) {
  if (routes === 'offline') mockNetworkDown();
  else mockApi(routes);
  await renderWithProviders(ui);
  await ready();
  await act(async () => {});
  expectAccessible();
}

const feedRoutes = (over: Routes = {}): Routes => ({
  'GET /api/v1/content/feed': { data: { items: [feedItem(1), feedItem(2)], next_cursor: null, total_unconsumed: 2 } },
  'GET /api/v1/sources': { data: { items: [source()] } },
  'GET /api/v1/sessions/active': { data: null },
  ...over,
});

describe('Queue', () => {
  it('with a feed and an active session', () =>
    audit(
      <QueueScreen />,
      feedRoutes({ 'GET /api/v1/sessions/active': { data: session({ status: 'in_progress' }) } }),
      () => screen.findByText('Fixture Workout Video #1')
    ));

  it('with no sources', () =>
    audit(
      <QueueScreen />,
      feedRoutes({
        'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
        'GET /api/v1/sources': { data: { items: [] } },
      }),
      () => screen.findByText('No Content Sources Added')
    ));

  it('all caught up', () =>
    audit(
      <QueueScreen />,
      feedRoutes({ 'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } } }),
      () => screen.findByText("You're All Caught Up!")
    ));

  it('offline', () => audit(<QueueScreen />, 'offline', () => screen.findByText('Network Connection Offline')));

  it('with the add-source sheet open', async () => {
    await audit(
      <QueueScreen />,
      feedRoutes({
        'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
        'GET /api/v1/sources': { data: { items: [] } },
      }),
      () => screen.findByText('No Content Sources Added')
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Add first playlist source' }));
    expectAccessible();
  });

  it('mid-sync', async () => {
    await audit(<QueueScreen />, feedRoutes(), () => screen.findByText('Fixture Workout Video #1'));
    await act(async () =>
      useQueueStore.setState({
        syncProgress: { ...useQueueStore.getState().syncProgress, isSyncing: true, itemsSyncedTotal: 250, estimatedTotal: 1284 },
      })
    );
    expectAccessible();
  });
});

describe('Match (content-first)', () => {
  beforeEach(() => setParams({ contentId: 'fx:fx_vid_3' }));
  const match = (over = {}) => ({
    data: {
      content_id: 'fx:fx_vid_3',
      duration_seconds: 1500,
      duration_label: '25m 0s',
      matching_activities: [activity('running'), activity('yoga')],
      is_valid: true,
      rejection_reason: null,
      ...over,
    },
  });

  it('with activities to pick', () =>
    audit(<MatchScreen />, { 'POST /api/v1/content/match': match() }, () => screen.findByText(/This item runs/)));

  it('when nothing fits', () =>
    audit(
      <MatchScreen />,
      {
        'POST /api/v1/content/match': match({
          is_valid: false,
          matching_activities: [],
          rejection_reason: 'duration_out_of_range',
        }),
      },
      () => screen.findByText('No Duration Match Found')
    ));

  it('after a load error', () =>
    audit(
      <MatchScreen />,
      { 'POST /api/v1/content/match': { status: 404, error: { code: 'CONTENT_NOT_FOUND', message: 'gone' } } },
      () => screen.findByText('This item is no longer in your queue.')
    ));

  it('when another session is active', async () => {
    await audit(
      <MatchScreen />,
      {
        'POST /api/v1/content/match': match(),
        'POST /api/v1/sessions': {
          status: 409,
          error: { code: 'ACTIVE_SESSION_EXISTS', message: 'busy', details: [{ field: 'session_id', issue: 's_9' }] },
        },
      },
      () => screen.findByText(/This item runs/)
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Start session' }));
    await screen.findByText('You already have a session in progress.');
    expectAccessible();
  });
});

describe('Time blocks (time-first)', () => {
  const catalog: Routes = {
    'GET /api/v1/activities/time-blocks': { data: { time_blocks: TIME_BLOCKS } },
    'GET /api/v1/activities': {
      data: { activities: [activity('running', 300, 14400, 'Run'), activity('strength', 600, 7200, 'Strength')] },
    },
  };
  const matched = (items = [feedItem(1, { duration_seconds: 1800, duration_label: '30m 0s' })]) => ({
    data: {
      target_duration_seconds: 1800,
      target_duration_label: '30m 0s',
      matched_items: items,
      window_type: items.length ? 'primary' : null,
      is_valid: items.length > 0,
      rejection_reason: items.length ? null : 'no_content_in_window',
    },
  });

  it('with a match', () =>
    audit(<BlocksScreen />, { ...catalog, 'POST /api/v1/content/match-time': matched() }, () =>
      screen.findByText('Fixture Workout Video #1')
    ));

  it('with no match', () =>
    audit(<BlocksScreen />, { ...catalog, 'POST /api/v1/content/match-time': matched([]) }, () =>
      screen.findByText('No Duration Match Found')
    ));

  it('when the catalog fails to load', () =>
    audit(<BlocksScreen />, 'offline', () => screen.findByText("Couldn't load time blocks")));
});

describe('Session checklist', () => {
  beforeEach(() => setParams({ id: 's_0001' }));

  it.each([1, 2] as const)('at step %s', (step) => {
    useSessionStore.setState({ currentSession: session(), currentStep: step });
    return audit(<SessionScreen />, {}, () => screen.findByRole('button', { name: 'Mark session complete' }));
  });

  it('in progress', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    await audit(
      <SessionScreen />,
      { 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress', started_at: '2026-01-01T10:00:00Z' }) } },
      () => screen.findByRole('button', { name: 'Launch Media and Start Workout Session' })
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Launch Media and Start Workout Session' }));
    await screen.findByText('Workout Target End Time');
    expectAccessible();
  });

  it('when the session is gone', () => {
    useSessionStore.setState({ currentSession: null });
    return audit(<SessionScreen />, { 'GET /api/v1/sessions/s_0001': { status: 404, error: { code: 'SESSION_NOT_FOUND', message: 'gone' } } }, () =>
      screen.findByText('Session not found')
    );
  });

  it('after the media app fails to open', async () => {
    (Linking.canOpenURL as jest.Mock).mockResolvedValue(false);
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    await audit(
      <SessionScreen />,
      { 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress' }) } },
      () => screen.findByRole('button', { name: 'Launch Media and Start Workout Session' })
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Launch Media and Start Workout Session' }));
    await screen.findByText(/Unable to launch YouTube/);
    expectAccessible();
  });
});

describe('History', () => {
  it('with sessions', () =>
    audit(
      <HistoryScreen />,
      {
        'GET /api/v1/sessions': {
          data: {
            items: [
              session({ id: 'a', status: 'completed' }),
              session({ id: 'b', status: 'abandoned', match_mode: 'time_first' }),
              session({ id: 'c', status: 'in_progress' }),
            ],
            next_cursor: null,
          },
        },
      },
      () => screen.findByText('Completed')
    ));

  it('empty', () =>
    audit(<HistoryScreen />, { 'GET /api/v1/sessions': { data: { items: [], next_cursor: null } } }, () =>
      screen.findByRole('button')
    ));
});

describe('Settings and sign-in', () => {
  it('settings, signed in', () => {
    resetStores({ user: { uid: 'u-123', email: 'me@x.com' } as never });
    return audit(<SettingsScreen />, {}, () => screen.findByText('me@x.com'));
  });

  it('sign-in', () => {
    resetStores({ isAuthenticated: false, user: null });
    return audit(<SignInScreen />, {}, () => screen.findByRole('button', { name: 'Sign in' }));
  });
});
