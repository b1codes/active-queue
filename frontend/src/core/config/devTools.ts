/**
 * Whether developer-only affordances (emulator quick sign-in, re-auth shortcuts) may be
 * shown. Never true in a production build unless the emulator is explicitly targeted:
 * `signInWithEmulator` falls back to *creating* test@activequeue.dev with a published
 * password, which must never happen against real Firebase Auth.
 */
export function isDevToolsEnabled(): boolean {
  const dev = typeof __DEV__ !== 'undefined' && __DEV__;
  return dev || process.env.EXPO_PUBLIC_USE_EMULATOR === 'true';
}
