import {
  combineReducers,
  configureStore,
  createAction,
  type Middleware,
  UnknownAction,
} from '@reduxjs/toolkit';
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

// Work that outlives a render (a sync loop, say) holds no state the reducer can reset, so
// it registers here to be told when the user changes and must stop.
const userScopeResetListeners = new Set<() => void>();

/** Calls `listener` after every resetUserScopedState. Returns an unsubscribe. */
export function onUserScopeReset(listener: () => void): () => void {
  userScopeResetListeners.add(listener);
  return () => userScopeResetListeners.delete(listener);
}

const notifyUserScopeReset: Middleware = () => (next) => (action) => {
  const result = next(action);
  if (resetUserScopedState.match(action)) {
    userScopeResetListeners.forEach((listener) => listener());
  }
  return result;
};

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
      }).concat(notifyUserScopeReset),
  });
}

export const store = createAppStore();

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
