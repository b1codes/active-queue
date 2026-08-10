import { useSessionStore } from '../features/sessions/sessionStore';
import * as sessionApi from '../features/sessions/sessionApi';
import * as deepLinks from '../features/sessions/deepLinks';

jest.mock('react-native', () => ({
  Linking: {
    canOpenURL: jest.fn(),
    openURL: jest.fn(),
  },
}));

jest.mock('../features/sessions/sessionApi');
jest.mock('../features/sessions/deepLinks');

describe('SessionStore Resumable Handoff State', () => {
  beforeEach(() => {
    useSessionStore.getState().clearSession();
    jest.clearAllMocks();
  });

  it('createNewSession creates pending session and sets step 1', async () => {
    const mockSession: sessionApi.Session = {
      id: 's100',
      user_id: 'u1',
      activity_id: 'running',
      match_mode: 'content_first',
      content_id: 'fx:1',
      duration_seconds: 1800,
      status: 'pending',
      checklist_completed: false,
      created_at: '2026-08-09T20:00:00Z',
      updated_at: '2026-08-09T20:00:00Z',
    };

    (sessionApi.createSession as jest.Mock).mockResolvedValue(mockSession);

    const res = await useSessionStore.getState().createNewSession({
      activity_id: 'running',
      match_mode: 'content_first',
      content_id: 'fx:1',
    });

    expect(res).toEqual(mockSession);
    expect(useSessionStore.getState().currentSession).toEqual(mockSession);
    expect(useSessionStore.getState().currentStep).toBe(1);
  });

  it('setSessionFromServer resumes directly at step 3 for in_progress session', () => {
    const activeSession: sessionApi.Session = {
      id: 's101',
      user_id: 'u1',
      activity_id: 'cycling',
      match_mode: 'time_first',
      duration_seconds: 2700,
      status: 'in_progress',
      checklist_completed: true,
      started_at: '2026-08-09T20:10:00Z',
      created_at: '2026-08-09T20:00:00Z',
      updated_at: '2026-08-09T20:10:00Z',
    };

    useSessionStore.getState().setSessionFromServer(activeSession);

    expect(useSessionStore.getState().currentStep).toBe(3);
    expect(useSessionStore.getState().currentSession?.status).toBe('in_progress');
  });

  it('skipTrackerStep advances to step 2', () => {
    useSessionStore.getState().skipTrackerStep();
    expect(useSessionStore.getState().currentStep).toBe(2);
  });

  it('startCurrentSession does NOT advance step on media deep link launch failure', async () => {
    const pendingSession: sessionApi.Session = {
      id: 's102',
      user_id: 'u1',
      activity_id: 'running',
      match_mode: 'content_first',
      content_id: 'fx:1',
      duration_seconds: 1800,
      status: 'pending',
      checklist_completed: false,
      created_at: '2026-08-09T20:00:00Z',
      updated_at: '2026-08-09T20:00:00Z',
    };

    const inProgressSession = { ...pendingSession, status: 'in_progress' as const };

    useSessionStore.setState({ currentSession: pendingSession, currentStep: 2 });

    (sessionApi.startSession as jest.Mock).mockResolvedValue(inProgressSession);
    (deepLinks.launchTrackerApp as jest.Mock).mockResolvedValue({
      success: false,
      launchedVia: 'fallback',
      error: 'Media app not installed',
    });

    const success = await useSessionStore.getState().startCurrentSession('youtube', '123');

    expect(success).toBe(false);
    expect(useSessionStore.getState().currentStep).toBe(2); // Retains step 2
    expect(useSessionStore.getState().mediaError).toBe('Media app not installed');
  });
});
