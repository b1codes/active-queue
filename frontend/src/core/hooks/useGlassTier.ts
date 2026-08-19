import { isLiquidGlassSupported } from '@callstack/liquid-glass';

/**
 * Liquid Glass tier resolution per llc-react/context/react-native-glass.md §0.
 *
 * Resolves once per app session (not per render) which glass rendering tier is
 * available, so every glass surface on a screen renders through the same tier
 * instead of mixing native material with a hand-rolled fallback.
 *
 * Tier 1 (@callstack/liquid-glass) is installed and wired: it resolves on iOS 26+
 * dev builds and renders the real OS UIVisualEffectView material. Tier 2
 * (@uginy/react-native-liquid-glass) is not installed yet — below iOS 26 and on
 * Android this still falls through to Tier 3 (hand-rolled Skia fallback).
 */
export type GlassTier = 1 | 2 | 3;

let cachedTier: GlassTier | null = null;

function isNativeMaterialSupported(): boolean {
  // Tier 1: wraps the real OS UIVisualEffectView liquid glass material (iOS 26+, RN 0.80+).
  // `isLiquidGlassSupported` is a boolean constant, not a function — on iOS it is read from
  // the native module's constants at import time; on every other platform the package ships
  // a `false` stub, so this is safe to evaluate unconditionally.
  return isLiquidGlassSupported;
}

function hasGpuShaderSupport(): boolean {
  // Tier 2: real-time AGSL/Metal shader refraction (New Architecture, iOS 15+/Android 13+,
  // Expo SDK 54+ dev build). TODO: once @uginy/react-native-liquid-glass is installed,
  // replace this with a real New Architecture + OS version capability check.
  return false;
}

function resolveGlassTier(): GlassTier {
  const tier: GlassTier = isNativeMaterialSupported() ? 1 : hasGpuShaderSupport() ? 2 : 3;
  if (__DEV__) {
    // Which tier a build actually landed on is invisible from the UI alone — a Tier 1
    // surface over an opaque backdrop looks much like the Tier 3 fallback. Log it once so
    // "is the native material live?" is answerable without instrumenting a screen.
    console.log(`[useGlassTier] resolved Tier ${tier} (isLiquidGlassSupported=${isLiquidGlassSupported})`);
  }
  return tier;
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

/**
 * Test-only: clears the cached tier so a suite can assert resolution under a
 * different mocked capability. Not used by app code.
 */
export function __resetGlassTierCacheForTests(): void {
  cachedTier = null;
}
