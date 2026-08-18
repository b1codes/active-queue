/**
 * Liquid Glass tier resolution per llc-react/context/react-native-glass.md §0.
 *
 * Resolves once per app session (not per render) which glass rendering tier is
 * available, so every glass surface on a screen renders through the same tier
 * instead of mixing native material with a hand-rolled fallback.
 *
 * Tier 1 (@callstack/liquid-glass) and Tier 2 (@uginy/react-native-liquid-glass)
 * are not yet installed — both require the Expo/RN version floors tracked in the
 * "Upgrade Expo SDK to 54+ / React Native to 0.80+" task. Until those land, this
 * always resolves to Tier 3 (hand-rolled Skia fallback) — the branches below are
 * the seam to wire the real packages into once they're available.
 */
export type GlassTier = 1 | 2 | 3;

let cachedTier: GlassTier | null = null;

function isNativeMaterialSupported(): boolean {
  // Tier 1: wraps the real OS UIVisualEffectView liquid glass material (iOS 26+, RN 0.80+).
  // TODO: once @callstack/liquid-glass is installed, replace this with its
  // `isLiquidGlassSupported` export instead of a hardcoded `false`.
  return false;
}

function hasGpuShaderSupport(): boolean {
  // Tier 2: real-time AGSL/Metal shader refraction (New Architecture, iOS 15+/Android 13+,
  // Expo SDK 54+ dev build). TODO: once @uginy/react-native-liquid-glass is installed,
  // replace this with a real New Architecture + OS version capability check.
  return false;
}

function resolveGlassTier(): GlassTier {
  if (isNativeMaterialSupported()) return 1;
  if (hasGpuShaderSupport()) return 2;
  return 3;
}

/**
 * Returns the glass tier to render through. Resolved once and cached for the
 * life of the app session — do not call the resolution logic per render.
 */
export function useGlassTier(): GlassTier {
  if (cachedTier === null) {
    cachedTier = resolveGlassTier();
  }
  return cachedTier;
}
