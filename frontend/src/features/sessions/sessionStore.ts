import { store } from '@/store';
import { useAppSelector } from '@/store/hooks';
import { ApiError } from '@/core/api/apiClient';
import {
  abandonSession,
  completeSession,
  createSession,
  CreateSessionInput,
  discardSession,
  getActiveSession,
  Session,
  startSession,
} from './sessionApi';
import { launchTrackerApp } from './deepLinks';
import {
  setSessionState,
  setSessionFromServer as setSessionFromServerAction,
  skipTrackerStep as skipTrackerStepAction,
  advanceStep as advanceStepAction,
  clearSession as clearSessionAction,
  SessionState,
  ChecklistStep,
} from './sessionSlice';

export type { ChecklistStep };

export interface SessionStoreActions {
  createNewSession: (input: CreateSessionInput) => Promise<Session | null>;
  completeCurrentSession: () => Promise<Session | null>;
  abandonCurrentSession: () => Promise<Session | null>;
  discardCurrentSession: () => Promise<boolean>;
  startCurrentSession: (trackerId: string, externalId?: string) => Promise<boolean>;
  skipTrackerStep: () => void;
  advanceStep: () => void;
  setSessionFromServer: (session: Session) => void;
  checkActiveSession: () => Promise<Session | null>;
  clearSession: () => void;
}

export function setSessionFromServer(session: Session): void {
  store.dispatch(setSessionFromServerAction(session));
}

export async function checkActiveSession(): Promise<Session | null> {
  try {
    const activeSession = await getActiveSession();
    if (activeSession) {
      setSessionFromServer(activeSession);
    } else {
      store.dispatch(setSessionState({ currentSession: null }));
    }
    return activeSession;
  } catch {
    return null;
  }
}

function failure(err: unknown, fallback: string) {
  const code = err instanceof ApiError ? err.code : 'UNKNOWN_ERROR';
  const conflict =
    err instanceof ApiError && err.code === 'ACTIVE_SESSION_EXISTS'
      ? err.details.find((d) => d.field === 'active_session_id')?.issue ?? null
      : null;
  return setSessionState({
    isLoading: false,
    error: err instanceof Error ? err.message : fallback,
    errorCode: code,
    conflictSessionId: conflict,
  });
}

export async function createNewSession(input: CreateSessionInput): Promise<Session | null> {
  store.dispatch(
    setSessionState({ isLoading: true, error: null, errorCode: null, conflictSessionId: null })
  );
  try {
    const session = await createSession(input);
    store.dispatch(
      setSessionState({
        currentSession: session,
        currentStep: 1,
        isLoading: false,
        error: null,
      })
    );
    return session;
  } catch (err: unknown) {
    store.dispatch(failure(err, 'Failed to create session'));
    return null;
  }
}

async function terminalTransition(
  call: (id: string) => Promise<Session>,
  fallback: string
): Promise<Session | null> {
  const { currentSession, isLoading } = store.getState().session;
  // Ignore double taps while a transition is in flight (the server is idempotent too).
  if (!currentSession || isLoading) return null;
  store.dispatch(setSessionState({ isLoading: true, error: null, errorCode: null }));
  try {
    const finished = await call(currentSession.id);
    store.dispatch(clearSessionAction());
    return finished;
  } catch (err: unknown) {
    store.dispatch(failure(err, fallback));
    return null;
  }
}

/** Step 4 "Mark Complete" (SPEC §6.2, §7.1). Consumes the content server-side. */
export function completeCurrentSession(): Promise<Session | null> {
  return terminalTransition(completeSession, 'Failed to complete session');
}

export function abandonCurrentSession(): Promise<Session | null> {
  return terminalTransition(abandonSession, 'Failed to abandon session');
}

/** Hard delete; only valid before the session is started (SPEC §7.1). */
export async function discardCurrentSession(): Promise<boolean> {
  const { currentSession, isLoading } = store.getState().session;
  if (!currentSession || isLoading) return false;
  store.dispatch(setSessionState({ isLoading: true, error: null, errorCode: null }));
  try {
    await discardSession(currentSession.id);
    store.dispatch(clearSessionAction());
    return true;
  } catch (err: unknown) {
    store.dispatch(failure(err, 'Failed to discard session'));
    return false;
  }
}

export function skipTrackerStep(): void {
  store.dispatch(skipTrackerStepAction());
}

export function advanceStep(): void {
  store.dispatch(advanceStepAction());
}

export async function startCurrentSession(
  mediaProvider: string,
  externalId?: string
): Promise<boolean> {
  const { currentSession } = store.getState().session;
  if (!currentSession) return false;

  store.dispatch(setSessionState({ isLoading: true, mediaError: null }));

  try {
    // 1. Call server POST /sessions/{id}/start per SPEC §6.2 & §9.5
    const updatedSession = await startSession(currentSession.id);

    // 2. Launch media app via deepLinks utility
    const launchRes = await launchTrackerApp(mediaProvider, externalId);

    if (!launchRes.success) {
      // The checklist stays on step 2 so the user can retry the launch (SPEC §6.3), but
      // the server has already recorded the start, so mirror that: a retry is an
      // idempotent re-start, and Mark Complete must not be told the session is pending.
      store.dispatch(
        setSessionState({
          currentSession: updatedSession,
          isLoading: false,
          mediaError: launchRes.error || 'Failed to launch media app. Please open manually.',
        })
      );
      return false;
    }

    store.dispatch(
      setSessionState({
        currentSession: updatedSession,
        currentStep: 3,
        isLoading: false,
        mediaError: null,
      })
    );
    return true;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Failed to start session';
    store.dispatch(setSessionState({ isLoading: false, mediaError: msg }));
    return false;
  }
}

export function clearSession(): void {
  store.dispatch(clearSessionAction());
}

const actions: SessionStoreActions = {
  createNewSession,
  completeCurrentSession,
  abandonCurrentSession,
  discardCurrentSession,
  startCurrentSession,
  skipTrackerStep,
  advanceStep,
  setSessionFromServer,
  checkActiveSession,
  clearSession,
};

export function useSessionStore<T = SessionState & SessionStoreActions>(
  selector?: (state: SessionState & SessionStoreActions) => T
): T {
  const sessionState = useAppSelector((state) => state.session);
  const combined = { ...sessionState, ...actions };

  if (selector) {
    return selector(combined as SessionState & SessionStoreActions);
  }

  return combined as unknown as T;
}

useSessionStore.getState = (): SessionState & SessionStoreActions => {
  return {
    ...store.getState().session,
    ...actions,
  };
};

useSessionStore.setState = (partialState: Partial<SessionState>): void => {
  store.dispatch(setSessionState(partialState));
};
