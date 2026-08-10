import { create } from 'zustand';
import { createSession, startSession, Session, CreateSessionInput } from './sessionApi';
import { launchTrackerApp } from './deepLinks';

export type ChecklistStep = 1 | 2 | 3;

interface SessionStoreState {
  currentSession: Session | null;
  currentStep: ChecklistStep;
  isLoading: boolean;
  error: string | null;
  trackerError: string | null;
  mediaError: string | null;
  
  // Actions
  createNewSession: (input: CreateSessionInput) => Promise<Session | null>;
  startCurrentSession: (trackerId: string, externalId?: string) => Promise<boolean>;
  skipTrackerStep: () => void;
  advanceStep: () => void;
  setSessionFromServer: (session: Session) => void;
  clearSession: () => void;
}

export const useSessionStore = create<SessionStoreState>((set, get) => ({
  currentSession: null,
  currentStep: 1,
  isLoading: false,
  error: null,
  trackerError: null,
  mediaError: null,

  setSessionFromServer: (session: Session) => {
    // Derive step from server state per SPEC §6.2
    let derivedStep: ChecklistStep = 1;
    if (session.status === 'in_progress' || session.checklist_completed) {
      derivedStep = 3;
    }

    set({
      currentSession: session,
      currentStep: derivedStep,
      error: null,
    });
  },

  createNewSession: async (input: CreateSessionInput) => {
    set({ isLoading: true, error: null });
    try {
      const session = await createSession(input);
      set({
        currentSession: session,
        currentStep: 1,
        isLoading: false,
        error: null,
      });
      return session;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create session';
      set({ isLoading: false, error: msg });
      return null;
    }
  },

  skipTrackerStep: () => {
    set({ currentStep: 2, trackerError: null });
  },

  advanceStep: () => {
    const { currentStep } = get();
    if (currentStep < 3) {
      set({ currentStep: (currentStep + 1) as ChecklistStep });
    }
  },

  startCurrentSession: async (mediaProvider: string, externalId?: string) => {
    const { currentSession } = get();
    if (!currentSession) return false;

    set({ isLoading: true, mediaError: null });

    try {
      // 1. Call server POST /sessions/{id}/start per SPEC §6.2 & §9.5
      const updatedSession = await startSession(currentSession.id);

      // 2. Launch media app via deepLinks utility
      const launchRes = await launchTrackerApp(mediaProvider, externalId);

      if (!launchRes.success) {
        // Do NOT transition session state on launch failure per subtask instruction
        set({
          isLoading: false,
          mediaError: launchRes.error || 'Failed to launch media app. Please open manually.',
        });
        return false;
      }

      set({
        currentSession: updatedSession,
        currentStep: 3,
        isLoading: false,
        mediaError: null,
      });
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start session';
      set({ isLoading: false, mediaError: msg });
      return false;
    }
  },

  clearSession: () => {
    set({
      currentSession: null,
      currentStep: 1,
      isLoading: false,
      error: null,
      trackerError: null,
      mediaError: null,
    });
  },
}));
