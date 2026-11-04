import React from 'react';
import { AppState, Linking } from 'react-native';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { resetRouter, router, setParams } from '@/test-utils/router';
import { mockApi, renderWithProviders, resetStores, session } from '@/test-utils';
import { useSessionStore } from '@/features/sessions/sessionStore';
import SessionScreen from '@app/(app)/session/[id]';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

let appStateListener: ((s: string) => void) | undefined;

beforeEach(() => {
  resetStores();
  resetRouter();
  setParams({ id: 's_0001' });
  jest.spyOn(Linking, 'canOpenURL').mockResolvedValue(true);
  jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
  jest.spyOn(AppState, 'addEventListener').mockImplementation(((_: string, cb: (s: string) => void) => {
    appStateListener = cb;
    return { remove: jest.fn() };
  }) as never);
});

const press = (name: string | RegExp) => fireEvent.press(screen.getByRole('button', { name }));

describe('session handoff checklist (SPEC §6.2)', () => {
  it('walks tracker -> media -> complete for a YouTube session', async () => {
    useSessionStore.setState({ currentSession: session({ activity_id: 'yoga' }), currentStep: 1 });
    const api = mockApi({
      'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress', started_at: '2026-01-01T10:00:00Z' }) },
      'POST /api/v1/sessions/s_0001/complete': { data: session({ status: 'completed' }) },
    });
    await renderWithProviders(<SessionScreen />);

    // Mark Complete is not available until the media step has run.
    expect(screen.getByRole('button', { name: 'Mark session complete' }).props.accessibilityState).toMatchObject({ disabled: true });

    await press('Open Tracker App'); // yoga -> guided "custom" tracker
    expect(useSessionStore.getState().currentStep).toBe(2);

    await press('Launch Media and Start Workout Session');
    expect(Linking.openURL).toHaveBeenCalledWith('youtube://watch?v=abc123');
    expect(screen.getByText('Workout Target End Time')).toBeTruthy();

    await press('Mark session complete');
    expect(api.callsTo('POST', '/api/v1/sessions/s_0001/complete')).toHaveLength(1);
    expect(router.replace).toHaveBeenCalledWith('/(app)/history');
  });

  it('fixture content plays through YouTube, not Spotify', async () => {
    useSessionStore.setState({ currentSession: session({ content_id: 'fx:fx_vid_7' }), currentStep: 2 });
    mockApi({ 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress' }) } });
    await renderWithProviders(<SessionScreen />);
    await press('Launch Media and Start Workout Session');
    expect(Linking.openURL).toHaveBeenCalledWith('youtube://watch?v=fx_vid_7');
  });

  it('a timer-only session starts without opening any app', async () => {
    useSessionStore.setState({ currentSession: session({ content_id: null, match_mode: 'time_first' }), currentStep: 2 });
    const api = mockApi({ 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress' }) } });
    await renderWithProviders(<SessionScreen />);
    await press('Launch Media and Start Workout Session');
    expect(api.calls).toHaveLength(1);
    expect(Linking.openURL).not.toHaveBeenCalled();
    expect(useSessionStore.getState().currentStep).toBe(3);
  });

  it('skipping the tracker goes straight to media', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 1 });
    await renderWithProviders(<SessionScreen />);
    await press('Skip Tracker Step');
    expect(useSessionStore.getState().currentStep).toBe(2);
    expect(screen.getByText('Completed / Skipped')).toBeTruthy();
  });

  it('returning from the tracker app advances the step', async () => {
    // Running uses the Apple Fitness guided entry: "launch" succeeds without a URL.
    useSessionStore.setState({ currentSession: session({ activity_id: 'running' }), currentStep: 1 });
    await renderWithProviders(<SessionScreen />);
    await press('Open Tracker App');
    // Simulate the store still showing step 1 when the app comes back to the foreground.
    await act(async () => useSessionStore.setState({ currentStep: 1 }));
    await act(async () => appStateListener?.('active'));
    expect(useSessionStore.getState().currentStep).toBe(2);
  });

  it('a failed media launch shows a retry and keeps step 2 (SPEC §6.3)', async () => {
    (Linking.canOpenURL as jest.Mock).mockResolvedValue(false);
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    mockApi({ 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress' }) } });
    await renderWithProviders(<SessionScreen />);
    await press('Launch Media and Start Workout Session');
    expect(screen.getByText(/Unable to launch YouTube/)).toBeTruthy();
    (Linking.canOpenURL as jest.Mock).mockResolvedValue(true);
    await press('Retry media launch');
    expect(useSessionStore.getState().currentStep).toBe(3);
  });

  it('abandon ends an in-progress session and returns to the queue', async () => {
    useSessionStore.setState({ currentSession: session({ status: 'in_progress' }), currentStep: 3 });
    mockApi({ 'POST /api/v1/sessions/s_0001/abandon': { data: session({ status: 'abandoned' }) } });
    await renderWithProviders(<SessionScreen />);
    expect(screen.queryByRole('button', { name: 'Discard session' })).toBeNull();
    await press('Abandon session');
    expect(router.replace).toHaveBeenCalledWith('/(app)');
  });

  it('discard is offered (instead of abandon) before the session starts', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 1 });
    mockApi({ 'DELETE /api/v1/sessions/s_0001': { data: { discarded: true } } });
    await renderWithProviders(<SessionScreen />);
    expect(screen.queryByRole('button', { name: 'Abandon session' })).toBeNull();
    await press('Discard session');
    expect(router.replace).toHaveBeenCalledWith('/(app)');
  });

  it('explains SESSION_NOT_STARTED in plain words', async () => {
    useSessionStore.setState({
      currentSession: session({ status: 'in_progress' }),
      currentStep: 3,
    });
    mockApi({
      'POST /api/v1/sessions/s_0001/complete': { status: 409, error: { code: 'SESSION_NOT_STARTED', message: 'raw' } },
    });
    await renderWithProviders(<SessionScreen />);
    await press('Mark session complete');
    expect(screen.getByText(/Open your media first/)).toBeTruthy();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe('cold start / deep link into a session', () => {
  it('rebuilds the session from the server when the store is empty', async () => {
    mockApi({ 'GET /api/v1/sessions/active': { data: session({ status: 'in_progress', started_at: '2026-01-01T10:00:00Z' }) } });
    await renderWithProviders(<SessionScreen />);
    await waitFor(() => expect(screen.getByText('Workout Target End Time')).toBeTruthy());
  });

  it('shows "Session not found" for a session that is no longer active', async () => {
    mockApi({ 'GET /api/v1/sessions/active': { data: null } });
    await renderWithProviders(<SessionScreen />);
    await waitFor(() => expect(screen.getByText('Session not found')).toBeTruthy());
    await press('Return to Queue Screen');
    expect(router.replace).toHaveBeenCalledWith('/(app)');
  });

  it('does not show another session than the one in the route', async () => {
    setParams({ id: 's_other' });
    useSessionStore.setState({ currentSession: session(), currentStep: 1 });
    mockApi({ 'GET /api/v1/sessions/active': { data: session() } });
    await renderWithProviders(<SessionScreen />);
    await waitFor(() => expect(screen.getByText('Session not found')).toBeTruthy());
  });
});
