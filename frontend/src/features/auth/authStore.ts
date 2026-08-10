import { store } from "@/store";
import { useAppSelector } from "@/store/hooks";
import { setAuthState, clearError as clearAuthSliceError, AuthState } from "./authSlice";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onIdTokenChanged,
} from "firebase/auth";
import { auth } from "./firebase";

export interface AuthActions {
  initAuth: () => () => void;
  signInWithEmulator: (email?: string, password?: string) => Promise<void>;
  signInWithEmail: (email: string, pass: string) => Promise<void>;
  signUpWithEmail: (email: string, pass: string) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

export function initAuth(): () => void {
  store.dispatch(setAuthState({ isLoading: true }));
  const unsubscribe = onIdTokenChanged(auth, async (currentUser) => {
    if (currentUser) {
      try {
        const token = await currentUser.getIdToken();
        store.dispatch(
          setAuthState({
            user: currentUser,
            idToken: token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to get auth token";
        store.dispatch(
          setAuthState({
            user: null,
            idToken: null,
            isAuthenticated: false,
            isLoading: false,
            error: message,
          })
        );
      }
    } else {
      store.dispatch(
        setAuthState({
          user: null,
          idToken: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        })
      );
    }
  });

  return unsubscribe;
}

export async function signInWithEmulator(
  email = "test@activequeue.dev",
  password = "password123"
): Promise<void> {
  store.dispatch(setAuthState({ isLoading: true, error: null }));
  try {
    await firebaseSignOut(auth);
  } catch {
    // Ignore sign-out error if no session active
  }
  try {
    await signInWithEmailAndPassword(auth, email, password);
  } catch {
    try {
      await createUserWithEmailAndPassword(auth, email, password);
    } catch (createErr: unknown) {
      const message = createErr instanceof Error ? createErr.message : "Sign-in failed";
      store.dispatch(setAuthState({ isLoading: false, error: message }));
    }
  }
}

export async function signInWithEmail(email: string, pass: string): Promise<void> {
  store.dispatch(setAuthState({ isLoading: true, error: null }));
  try {
    await signInWithEmailAndPassword(auth, email, pass);
  } catch (_err: unknown) {
    const message = _err instanceof Error ? _err.message : "Sign-in failed";
    store.dispatch(setAuthState({ isLoading: false, error: message }));
    throw _err;
  }
}

export async function signUpWithEmail(email: string, pass: string): Promise<void> {
  store.dispatch(setAuthState({ isLoading: true, error: null }));
  try {
    await createUserWithEmailAndPassword(auth, email, pass);
  } catch (_err: unknown) {
    const message = _err instanceof Error ? _err.message : "Sign-up failed";
    store.dispatch(setAuthState({ isLoading: false, error: message }));
    throw _err;
  }
}

export async function signOut(): Promise<void> {
  store.dispatch(setAuthState({ isLoading: true }));
  try {
    await firebaseSignOut(auth);
    store.dispatch(
      setAuthState({
        user: null,
        idToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      })
    );
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Sign-out failed";
    store.dispatch(setAuthState({ isLoading: false, error: message }));
  }
}

export function clearError(): void {
  store.dispatch(clearAuthSliceError());
}

const actions: AuthActions = {
  initAuth,
  signInWithEmulator,
  signInWithEmail,
  signUpWithEmail,
  signOut,
  clearError,
};

export function useAuthStore<T = AuthState & AuthActions>(
  selector?: (state: AuthState & AuthActions) => T
): T {
  const authState = useAppSelector((state) => state.auth);
  const combined = { ...authState, ...actions };

  if (selector) {
    return selector(combined as AuthState & AuthActions);
  }

  return combined as unknown as T;
}

useAuthStore.getState = (): AuthState & AuthActions => {
  return {
    ...store.getState().auth,
    ...actions,
  };
};

useAuthStore.setState = (partialState: Partial<AuthState>): void => {
  store.dispatch(setAuthState(partialState));
};
