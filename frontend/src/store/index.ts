import { combineReducers, configureStore, createAction, UnknownAction } from '@reduxjs/toolkit';
import { authSlice } from '../features/auth/authSlice';
import { queueSlice } from '../features/queue/queueSlice';
import { sessionSlice } from '../features/sessions/sessionSlice';

/**
 * Drops everything that belongs to the signed-in user (feed, sync progress, active
 * session) back to initial state. Dispatched whenever the authenticated uid changes,
 * including sign-out, so the next account never sees the previous account's queue
 * or active-session banner, even briefly or when the first fetch fails.
 */
export const resetUserScopedState = createAction('app/resetUserScopedState');

const slices = combineReducers({
  auth: authSlice.reducer,
  queue: queueSlice.reducer,
  session: sessionSlice.reducer,
});

type SlicesState = ReturnType<typeof slices>;

function rootReducer(state: SlicesState | undefined, action: UnknownAction): SlicesState {
  if (resetUserScopedState.match(action) && state) {
    return slices({ auth: state.auth } as SlicesState, action);
  }
  return slices(state, action);
}

export function createAppStore() {
  return configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({
        serializableCheck: false,
      }),
  });
}

export const store = createAppStore();

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
