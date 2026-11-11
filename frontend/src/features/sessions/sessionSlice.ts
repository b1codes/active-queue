import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { Session } from './sessionApi';

export type ChecklistStep = 1 | 2 | 3;

export interface SessionState {
  currentSession: Session | null;
  currentStep: ChecklistStep;
  isLoading: boolean;
  error: string | null;
  /** ApiError code behind `error`, e.g. ACTIVE_SESSION_EXISTS or SESSION_NOT_STARTED. */
  errorCode: string | null;
  /** For ACTIVE_SESSION_EXISTS: the session that blocks creation, so the UI can offer Resume. */
  conflictSessionId: string | null;
  trackerError: string | null;
  mediaError: string | null;
}

const initialState: SessionState = {
  currentSession: null,
  currentStep: 1,
  isLoading: false,
  error: null,
  errorCode: null,
  conflictSessionId: null,
  trackerError: null,
  mediaError: null,
};

export const sessionSlice = createSlice({
  name: 'session',
  initialState,
  reducers: {
    setSessionState: (state, action: PayloadAction<Partial<SessionState>>) => {
      Object.assign(state, action.payload);
    },
    setSessionFromServer: (state, action: PayloadAction<Session>) => {
      let derivedStep: ChecklistStep = 1;
      if (action.payload.status === 'in_progress' || action.payload.checklist_completed) {
        derivedStep = 3;
      }
      state.currentSession = action.payload;
      state.currentStep = derivedStep;
      state.error = null;
      state.errorCode = null;
    },
    skipTrackerStep: (state) => {
      state.currentStep = 2;
      state.trackerError = null;
    },
    /**
     * Advance one step. With `from`, only if the checklist is still on that step: two taps
     * on "Open Tracker" both finish step 1, and the second must not also finish step 2
     * (the media launch and server start), which would leave the session never started.
     */
    advanceStep: (state, action: PayloadAction<ChecklistStep | undefined>) => {
      if (action.payload !== undefined && state.currentStep !== action.payload) return;
      if (state.currentStep < 3) {
        state.currentStep = (state.currentStep + 1) as ChecklistStep;
      }
    },
    clearSession: () => initialState,
  },
});

export const {
  setSessionState,
  setSessionFromServer,
  skipTrackerStep,
  advanceStep,
  clearSession,
} = sessionSlice.actions;
