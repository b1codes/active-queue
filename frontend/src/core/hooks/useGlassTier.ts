import { isLiquidGlassSupported } from '@callstack/liquid-glass';

/**
 * Liquid Glass tier resolution per llc-react/context/react-native-glass.md §0.
 *
 * Resolves once per app session (not per render) which glass rendering tier is
 * available, so every glass surface on a screen renders through the same tier
 * instead of mixing native material with a shader or hand-rolled fallback.
 *
 * - Tier 1 (@callstack/liquid-glass): iOS 26+ dev builds — real OS UIVisualEffectView material.
 * - Tier 2 (@uginy/react-native-liquid-glass): evaluated and rejected on both platforms, so it
 *   never resolves today (see hasGpuShaderSupport). The tier number stays reserved so a future
 *   shader backend slots in without renumbering.
 * - Tier 3 (@shopify/react-native-skia): fallback for everything else. RN Skia's BackdropFilter
 *   only filters content already drawn in the same Canvas, not the native views behind it, so
 *   over real screen content this renders a translucent glassSurface fill + specular stroke,
 *   not a true backdrop blur.
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
  // Tier 2: @uginy/react-native-liquid-glass@1.2.6 was evaluated and rejected on both platforms.
  // - iOS: findBackdropSource (ios/LiquidGlassView.swift) only samples UIImageView backdrops and
  //   renders fully transparent over View/FlatList content (verified on the iOS 18.6 simulator).
  // - Android: LiquidGlassView.kt draws one static backdrop bitmap, shared by every instance and
  //   only re-captured once all instances unmount, and paints it opaque (res.a = 1.0) — so the
  //   glass freezes over a stale frame and hides the live list scrolling beneath it. The capture
  //   source also prefers the largest ImageView (e.g. a single feed thumbnail) over the real
  //   background, and includes each surface's own children, ghosting them behind themselves.
  // Revisit if the package re-captures live content; until then every non-Tier-1 runtime uses Tier 3.
  return false;
}

function resolveGlassTier(): GlassTier {
  const tier: GlassTier = isNativeMaterialSupported() ? 1 : hasGpuShaderSupport() ? 2 : 3;
  if (__DEV__) {
    // Which tier a build actually landed on is invisible from the UI alone — a Tier 1
    // surface over an opaque backdrop looks much like the Tier 3 fallback. Log it once so
    // "is the native material live?" is answerable without instrumenting a screen.
    // eslint-disable-next-line no-console
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
