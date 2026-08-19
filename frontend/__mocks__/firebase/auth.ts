// Manual mock for the "firebase/auth" subpath used under Jest — see app.ts in
// this directory for why the real SDK is stubbed rather than parsed.
export type User = {
  uid: string;
  getIdToken: (forceRefresh?: boolean) => Promise<string>;
};

export const initializeAuth = jest.fn(() => ({}));
export const getAuth = jest.fn(() => ({}));
export const connectAuthEmulator = jest.fn();
export const signInWithEmailAndPassword = jest.fn();
export const createUserWithEmailAndPassword = jest.fn();
export const signOut = jest.fn();
export const onIdTokenChanged = jest.fn(() => () => {});
