import { create } from "zustand";
import {
  User,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { auth } from "./firebase";

interface AuthState {
  user: User | null;
  idToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  initAuth: () => () => void;
  signInWithEmulator: (email?: string, password?: string) => Promise<void>;
  signInWithEmail: (email: string, pass: string) => Promise<void>;
  signUpWithEmail: (email: string, pass: string) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  idToken: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  initAuth: () => {
    set({ isLoading: true });
    const unsubscribe = onIdTokenChanged(auth, async (currentUser) => {
      if (currentUser) {
        try {
          const token = await currentUser.getIdToken();
          set({
            user: currentUser,
            idToken: token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : "Failed to get auth token";
          set({
            user: null,
            idToken: null,
            isAuthenticated: false,
            isLoading: false,
            error: message,
          });
        }
      } else {
        set({
          user: null,
          idToken: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      }
    });

    return unsubscribe;
  },

  signInWithEmulator: async (email = "test@activequeue.dev", password = "password123") => {
    set({ isLoading: true, error: null });
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } catch {
      // If emulator user does not exist yet, create it on the fly
      try {
        await createUserWithEmailAndPassword(auth, email, password);
      } catch (createErr: unknown) {
        const message = createErr instanceof Error ? createErr.message : "Sign-in failed";
        set({ isLoading: false, error: message });
      }
    }
  },

  signInWithEmail: async (email: string, pass: string) => {
    set({ isLoading: true, error: null });
    try {
      await signInWithEmailAndPassword(auth, email, pass);
    } catch (_err: unknown) {
      const message = _err instanceof Error ? _err.message : "Sign-in failed";
      set({ isLoading: false, error: message });
      throw _err;
    }
  },

  signUpWithEmail: async (email: string, pass: string) => {
    set({ isLoading: true, error: null });
    try {
      await createUserWithEmailAndPassword(auth, email, pass);
    } catch (_err: unknown) {
      const message = _err instanceof Error ? _err.message : "Sign-up failed";
      set({ isLoading: false, error: message });
      throw _err;
    }
  },

  signOut: async () => {
    set({ isLoading: true });
    try {
      await firebaseSignOut(auth);
      set({
        user: null,
        idToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Sign-out failed";
      set({ isLoading: false, error: message });
    }
  },

  clearError: () => set({ error: null }),
}));
