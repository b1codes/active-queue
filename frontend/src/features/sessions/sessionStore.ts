import { store } from '@/store';
import { useAppSelector } from '@/store/hooks';
import { createSession, startSession, getActiveSession, Session, CreateSessionInput } from './sessionApi';
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

export async function createNewSession(input: CreateSessionInput): Promise<Session | null> {
  store.dispatch(setSessionState({ isLoading: true, error: null }));
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
    const msg = err instanceof Error ? err.message : 'Failed to create session';
    store.dispatch(setSessionState({ isLoading: false, error: msg }));
    return null;
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
      // Do NOT transition session state on launch failure per subtask instruction
      store.dispatch(
        setSessionState({
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
