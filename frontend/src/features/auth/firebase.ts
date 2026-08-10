import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, connectAuthEmulator } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY || "fake-api-key",
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN || "auth.activequeue.app",
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID || "activequeue-local",
};

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);

// Wire Auth emulator in local/dev mode per SPEC §3.1
const isDev = typeof __DEV__ !== "undefined" ? __DEV__ : process.env.NODE_ENV !== "production";
const emulatorHost = process.env.EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST || "http://127.0.0.1:9099";

if (isDev || process.env.EXPO_PUBLIC_USE_EMULATOR === "true") {
  try {
    connectAuthEmulator(auth, emulatorHost, { disableWarnings: true });
  } catch {
    // Emulator already connected in HMR cycle
  }
}

export default app;
