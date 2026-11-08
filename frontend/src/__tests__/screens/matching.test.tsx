import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { resetRouter, router, setParams } from '@/test-utils/router';
import {
  activity,
  feedItem,
  mockApi,
  mockNetworkDown,
  renderWithProviders,
  resetStores,
  session,
  TIME_BLOCKS,
} from '@/test-utils';
import MatchScreen from '@app/(app)/match/[contentId]';
import BlocksScreen from '@app/(app)/blocks';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

beforeEach(() => {
  resetStores();
  resetRouter();
});

const press = (name: string | RegExp) => fireEvent.press(screen.getByRole('button', { name }));

describe('MatchScreen (content-first, SPEC §5.2)', () => {
  beforeEach(() => setParams({ contentId: 'fx:fx_vid_3' }));

  const valid = {
    data: {
      content_id: 'fx:fx_vid_3',
      duration_seconds: 1500,
      duration_label: '25m 0s',
      matching_activities: [activity('running'), activity('yoga')],
      is_valid: true,
      rejection_reason: null,
    },
  };

  it('lists fitting activities and creates a content_first session for the choice', async () => {
    const api = mockApi({
      'POST /api/v1/content/match': valid,
      'POST /api/v1/sessions': { status: 201, data: session({ id: 's_new' }) },
    });
    await renderWithProviders(<MatchScreen />);
    await screen.findByText(/This item runs 25m 0s/);
    expect(screen.getByRole('radio', { name: 'Running' }).props.accessibilityState).toMatchObject({ checked: true });

    await fireEvent.press(screen.getByRole('radio', { name: 'Yoga' }));
    await press('Start session');
    expect(api.callsTo('POST', '/api/v1/sessions')[0].body).toEqual({
      activity_id: 'yoga',
      match_mode: 'content_first',
      content_id: 'fx:fx_vid_3',
    });
    expect(router.push).toHaveBeenCalledWith({ pathname: '/(app)/session/[id]', params: { id: 's_new' } });
  });

  it('shows the no-match state with the reason', async () => {
    mockApi({
      'POST /api/v1/content/match': {
        data: { ...valid.data, matching_activities: [], is_valid: false, rejection_reason: 'duration_out_of_range' },
      },
    });
    await renderWithProviders(<MatchScreen />);
    expect(await screen.findByText(/between 5 minutes/)).toBeTruthy();
    await press('Try a different duration');
    expect(router.back).toHaveBeenCalled();
  });

  it('offers Resume when another session is already active', async () => {
    mockApi({
      'POST /api/v1/content/match': valid,
      'POST /api/v1/sessions': {
        status: 409,
        error: { code: 'ACTIVE_SESSION_EXISTS', message: 'x', details: [{ field: 'active_session_id', issue: 's_live' }] },
      },
    });
    await renderWithProviders(<MatchScreen />);
    await screen.findByText(/This item runs/);
    await press('Start session');
    expect(screen.getByText('You already have a session in progress.')).toBeTruthy();
    await press('Resume active session');
    expect(router.push).toHaveBeenCalledWith({ pathname: '/(app)/session/[id]', params: { id: 's_live' } });
  });

  it('explains a missing item and retries other failures', async () => {
    mockApi({
      'POST /api/v1/content/match': [
        { status: 404, error: { code: 'CONTENT_NOT_FOUND', message: 'gone' } },
        valid,
      ],
    });
    await renderWithProviders(<MatchScreen />);
    expect(await screen.findByText('This item is no longer in your queue.')).toBeTruthy();
    await press('Retry loading matches');
    expect(await screen.findByText(/This item runs/)).toBeTruthy();
  });

  it('shows network failures', async () => {
    mockNetworkDown();
    await renderWithProviders(<MatchScreen />);
    expect(await screen.findByText(/Network request failed/)).toBeTruthy();
  });
});

describe('BlocksScreen (time-first, SPEC §5.3)', () => {
  const catalog = {
    'GET /api/v1/activities/time-blocks': { data: { time_blocks: TIME_BLOCKS } },
    'GET /api/v1/activities': {
      data: {
        activities: [
          activity('running', 300, 14400, 'Run'),
          activity('strength', 600, 7200, 'Strength'),
          { ...activity('retired'), is_active: false },
        ],
      },
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

  it('loads the real catalog, hides inactive activities, and asks the server for matches', async () => {
    const api = mockApi({ ...catalog, 'POST /api/v1/content/match-time': matched() });
    await renderWithProviders(<BlocksScreen />);
    expect(await screen.findByRole('radio', { name: 'Target duration 30 min' })).toBeTruthy();
    expect(screen.queryByRole('radio', { name: 'Activity Retired' })).toBeNull();
    await screen.findByText('Fixture Workout Video #1');
    expect(api.callsTo('POST', '/api/v1/content/match-time')[0].body).toEqual({ target_duration_seconds: 1800 });
  });

  it('only offers activities whose bounds fit the block', async () => {
    mockApi({ ...catalog, 'POST /api/v1/content/match-time': matched() });
    await renderWithProviders(<BlocksScreen />);
    await fireEvent.press(await screen.findByRole('radio', { name: 'Target duration 90 min' }));
    // strength max is 7200s, so it still fits 5400s; both shown.
    expect(screen.getByRole('radio', { name: 'Activity Strength' })).toBeTruthy();
  });

  it('starts a time_first session with the matched media', async () => {
    const api = mockApi({
      ...catalog,
      'POST /api/v1/content/match-time': matched(),
      'POST /api/v1/sessions': { status: 201, data: session({ id: 's_tf' }) },
    });
    await renderWithProviders(<BlocksScreen />);
    await screen.findByText('Fixture Workout Video #1');
    await fireEvent(screen.getByTestId('start-matched-session'), 'accessibilityAction', {
      nativeEvent: { actionName: 'activate' },
    });
    await waitFor(() => expect(router.push).toHaveBeenCalled());
    expect(api.callsTo('POST', '/api/v1/sessions')[0].body).toEqual({
      activity_id: 'running',
      match_mode: 'time_first',
      content_id: 'fx:fx_vid_1',
      target_duration_seconds: null,
    });
  });

  it('shows the no-match state and still allows a timer-only session', async () => {
    const api = mockApi({
      ...catalog,
      'POST /api/v1/content/match-time': matched([]),
      'POST /api/v1/sessions': { status: 201, data: session({ id: 's_bare', content_id: null }) },
    });
    await renderWithProviders(<BlocksScreen />);
    expect(await screen.findByText(/No unconsumed feed items fit/)).toBeTruthy();
    await press('Start a timer-only session');
    expect(api.callsTo('POST', '/api/v1/sessions')[0].body).toEqual({
      activity_id: 'running',
      match_mode: 'time_first',
      content_id: null,
      target_duration_seconds: 1800,
    });
  });

  it('labels a fallback-window match as slightly shorter', async () => {
    const res = matched([feedItem(1, { duration_seconds: 1700, duration_label: '28m 20s' })]);
    res.data.window_type = 'fallback';
    mockApi({ ...catalog, 'POST /api/v1/content/match-time': res });
    await renderWithProviders(<BlocksScreen />);
    expect(await screen.findByText(/Slightly shorter/)).toBeTruthy();
  });

  it('offers Resume when another session is active', async () => {
    mockApi({
      ...catalog,
      'POST /api/v1/content/match-time': matched([]),
      'POST /api/v1/sessions': {
        status: 409,
        error: { code: 'ACTIVE_SESSION_EXISTS', message: 'x', details: [{ field: 'active_session_id', issue: 's_live' }] },
      },
    });
    await renderWithProviders(<BlocksScreen />);
    await screen.findByText(/No unconsumed feed items fit/);
    await press('Start a timer-only session');
    await press('Resume active session');
    expect(router.push).toHaveBeenCalledWith({ pathname: '/(app)/session/[id]', params: { id: 's_live' } });
  });

  it('shows a retryable error when the catalog cannot load', async () => {
    mockApi({
      'GET /api/v1/activities/time-blocks': [{ status: 503, error: { code: 'X', message: 'down' } }, catalog['GET /api/v1/activities/time-blocks']],
      'GET /api/v1/activities': catalog['GET /api/v1/activities'],
      'POST /api/v1/content/match-time': { status: 503, error: { code: 'X', message: 'down' } },
    });
    await renderWithProviders(<BlocksScreen />);
    expect(await screen.findByText("Couldn't load time blocks")).toBeTruthy();
    await press('Retry loading time blocks');
    expect(await screen.findByRole('radio', { name: 'Target duration 30 min' })).toBeTruthy();
  });
});
