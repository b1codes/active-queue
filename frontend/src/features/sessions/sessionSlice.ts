import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { Session } from './sessionApi';

export type ChecklistStep = 1 | 2 | 3;

export interface SessionState {
  currentSession: Session | null;
  currentStep: ChecklistStep;
  isLoading: boolean;
  error: string | null;
  trackerError: string | null;
  mediaError: string | null;
}

const initialState: SessionState = {
  currentSession: null,
  currentStep: 1,
  isLoading: false,
  error: null,
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
    },
    skipTrackerStep: (state) => {
      state.currentStep = 2;
      state.trackerError = null;
    },
    advanceStep: (state) => {
      if (state.currentStep < 3) {
        state.currentStep = (state.currentStep + 1) as ChecklistStep;
      }
    },
    clearSession: (state) => {
      state.currentSession = null;
      state.currentStep = 1;
      state.isLoading = false;
      state.error = null;
      state.trackerError = null;
      state.mediaError = null;
    },
  },
});

export const {
  setSessionState,
  setSessionFromServer,
  skipTrackerStep,
  advanceStep,
  clearSession,
} = sessionSlice.actions;
