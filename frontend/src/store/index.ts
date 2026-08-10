import { configureStore } from '@reduxjs/toolkit';
import { authSlice } from '../features/auth/authSlice';
import { queueSlice } from '../features/queue/queueSlice';
import { sessionSlice } from '../features/sessions/sessionSlice';

export const store = configureStore({
  reducer: {
    auth: authSlice.reducer,
    queue: queueSlice.reducer,
    session: sessionSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: false,
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
