import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import {
  User,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { auth } from "./firebase";

export interface AuthState {
  user: User | null;
  idToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  idToken: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
};

export const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setAuthState: (state, action: PayloadAction<Partial<AuthState>>) => {
      Object.assign(state, action.payload);
    },
    clearError: (state) => {
      state.error = null;
    },
  },
});

export const { setAuthState, clearError } = authSlice.actions;
