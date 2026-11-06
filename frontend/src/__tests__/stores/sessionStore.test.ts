import { Linking } from 'react-native';
import { store } from '@/store';
import {
  abandonCurrentSession,
  advanceStep,
  checkActiveSession,
  clearSession,
  completeCurrentSession,
  createNewSession,
  discardCurrentSession,
  setSessionFromServer,
  skipTrackerStep,
  startCurrentSession,
  useSessionStore,
} from '@/features/sessions/sessionStore';
import { mockApi, mockNetworkDown, resetStores, session } from '@/test-utils';

const state = () => store.getState().session;

beforeEach(() => {
  resetStores();
  jest.spyOn(Linking, 'canOpenURL').mockResolvedValue(true);
  jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
});

describe('createNewSession', () => {
  it('stores the new session at step 1', async () => {
    const api = mockApi({ 'POST /api/v1/sessions': { status: 201, data: session() } });
    const created = await createNewSession({ activity_id: 'running', match_mode: 'content_first', content_id: 'yt:abc123' });
    expect(created?.id).toBe('s_0001');
    expect(state()).toMatchObject({ currentStep: 1, isLoading: false, error: null });
    expect(api.calls[0].body).toEqual({ activity_id: 'running', match_mode: 'content_first', content_id: 'yt:abc123' });
  });

  it('exposes the blocking session id on ACTIVE_SESSION_EXISTS so the UI can offer Resume', async () => {
    mockApi({
      'POST /api/v1/sessions': {
        status: 409,
        error: {
          code: 'ACTIVE_SESSION_EXISTS',
          message: 'active',
          details: [{ field: 'active_session_id', issue: 's_blocking' }],
        },
      },
    });
    expect(await createNewSession({ activity_id: 'running', match_mode: 'time_first', target_duration_seconds: 900 })).toBeNull();
    expect(state()).toMatchObject({ errorCode: 'ACTIVE_SESSION_EXISTS', conflictSessionId: 's_blocking', isLoading: false });
  });

  it('reports network failure without a conflict id', async () => {
    mockNetworkDown();
    await createNewSession({ activity_id: 'running', match_mode: 'time_first', target_duration_seconds: 900 });
    expect(state()).toMatchObject({ errorCode: 'NETWORK_UNAVAILABLE', conflictSessionId: null });
  });
});

describe('checklist steps (SPEC §6.2)', () => {
  it('derives step 3 from server state so progress survives a restart', () => {
    setSessionFromServer(session({ status: 'in_progress', started_at: '2026-01-01T10:01:00Z' }));
    expect(state().currentStep).toBe(3);
    setSessionFromServer(session({ status: 'pending' }));
    expect(state().currentStep).toBe(1);
  });

  it('skip and advance move forward but never past step 3', () => {
    setSessionFromServer(session());
    skipTrackerStep();
    expect(state().currentStep).toBe(2);
    advanceStep();
    advanceStep();
    expect(state().currentStep).toBe(3);
  });

  it('checkActiveSession loads the active session or clears a stale one', async () => {
    mockApi({ 'GET /api/v1/sessions/active': [{ data: session({ status: 'in_progress' }) }, { data: null }] });
    expect((await checkActiveSession())?.id).toBe('s_0001');
    expect(state().currentSession?.id).toBe('s_0001');
    expect(await checkActiveSession()).toBeNull();
    expect(state().currentSession).toBeNull();
  });

  it('checkActiveSession swallows network errors', async () => {
    mockNetworkDown();
    await expect(checkActiveSession()).resolves.toBeNull();
  });
});

describe('startCurrentSession', () => {
  it('starts on the server, launches media, and moves to step 3', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    mockApi({ 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress', started_at: 'x' }) } });
    expect(await startCurrentSession('youtube', 'abc123')).toBe(true);
    expect(Linking.openURL).toHaveBeenCalledWith('youtube://watch?v=abc123');
    expect(state()).toMatchObject({ currentStep: 3, mediaError: null });
  });

  it('keeps step 2 with a retryable error when the media app cannot open, but mirrors the server start', async () => {
    (Linking.canOpenURL as jest.Mock).mockResolvedValue(false);
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    mockApi({ 'POST /api/v1/sessions/s_0001/start': { data: session({ status: 'in_progress' }) } });
    expect(await startCurrentSession('youtube', 'abc123')).toBe(false);
    expect(state().currentStep).toBe(2);
    expect(state().mediaError).toMatch(/YouTube/);
    expect(state().currentSession?.status).toBe('in_progress');
  });

  it('reports a server failure as a media error', async () => {
    useSessionStore.setState({ currentSession: session(), currentStep: 2 });
    mockNetworkDown();
    expect(await startCurrentSession('youtube', 'abc123')).toBe(false);
    expect(state().mediaError).toMatch(/Network/);
  });

  it('does nothing without a current session', async () => {
    expect(await startCurrentSession('youtube')).toBe(false);
  });
});

describe('terminal transitions', () => {
  it('complete clears the session', async () => {
    useSessionStore.setState({ currentSession: session({ status: 'in_progress' }) });
    mockApi({ 'POST /api/v1/sessions/s_0001/complete': { data: session({ status: 'completed' }) } });
    expect((await completeCurrentSession())?.status).toBe('completed');
    expect(state().currentSession).toBeNull();
  });

  it('complete before start surfaces SESSION_NOT_STARTED and keeps the session', async () => {
    useSessionStore.setState({ currentSession: session() });
    mockApi({
      'POST /api/v1/sessions/s_0001/complete': { status: 409, error: { code: 'SESSION_NOT_STARTED', message: 'nope' } },
    });
    expect(await completeCurrentSession()).toBeNull();
    expect(state()).toMatchObject({ errorCode: 'SESSION_NOT_STARTED', isLoading: false });
    expect(state().currentSession?.id).toBe('s_0001');
  });

  it('ignores a second tap while a transition is in flight', async () => {
    useSessionStore.setState({ currentSession: session({ status: 'in_progress' }) });
    const api = mockApi({ 'POST /api/v1/sessions/s_0001/complete': { data: session({ status: 'completed' }) } });
    const first = completeCurrentSession();
    const second = completeCurrentSession();
    await Promise.all([first, second]);
    expect(api.calls).toHaveLength(1);
  });

  it('abandon and discard clear the session', async () => {
    useSessionStore.setState({ currentSession: session({ status: 'in_progress' }) });
    mockApi({
      'POST /api/v1/sessions/s_0001/abandon': { data: session({ status: 'abandoned' }) },
      'DELETE /api/v1/sessions/s_0001': { data: { session_id: 's_0001', discarded: true } },
    });
    expect((await abandonCurrentSession())?.status).toBe('abandoned');
    expect(state().currentSession).toBeNull();

    useSessionStore.setState({ currentSession: session() });
    expect(await discardCurrentSession()).toBe(true);
    expect(state().currentSession).toBeNull();
  });

  it('discard failure keeps the session and reports the code', async () => {
    useSessionStore.setState({ currentSession: session({ status: 'in_progress' }) });
    mockApi({
      'DELETE /api/v1/sessions/s_0001': { status: 409, error: { code: 'SESSION_ALREADY_STARTED', message: 'x' } },
    });
    expect(await discardCurrentSession()).toBe(false);
    expect(state().errorCode).toBe('SESSION_ALREADY_STARTED');
  });

  it('transitions are no-ops without a session', async () => {
    expect(await completeCurrentSession()).toBeNull();
    expect(await discardCurrentSession()).toBe(false);
  });

  it('clearSession resets everything', () => {
    useSessionStore.setState({ currentSession: session(), error: 'x', errorCode: 'Y', currentStep: 3 });
    clearSession();
    expect(state()).toMatchObject({ currentSession: null, error: null, errorCode: null, currentStep: 1 });
  });
});
