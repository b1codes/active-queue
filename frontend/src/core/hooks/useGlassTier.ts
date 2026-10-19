import { isLiquidGlassSupported } from '@callstack/liquid-glass';
import { requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';

/**
 * Liquid Glass tier resolution per llc-react/context/react-native-glass.md §0.
 *
 * Resolves once per app session (not per render) which glass rendering tier is
 * available, so every glass surface on a screen renders through the same tier
 * instead of mixing native material with a shader or hand-rolled fallback.
 *
 * - Tier 1 (@callstack/liquid-glass): iOS 26+ dev builds — real OS UIVisualEffectView material.
 * - Tier 2 (@uginy/react-native-liquid-glass): Android 13+ (API 33+) dev builds with New
 *   Architecture (Fabric) enabled — real-time AGSL RuntimeShader refraction.
 *   Note: although @uginy/react-native-liquid-glass ships an iOS 15+ Metal view, its
 *   `findBackdropSource` (ios/LiquidGlassView.swift) rejects any backdrop that is not a
 *   `UIImageView` covering >=15% of the window and renders 100% transparent over `<View>` /
 *   `<FlatList>` hierarchies (verified on iOS 18.6 simulator). iOS < 26 therefore falls through
 *   to Tier 3, whose Skia `BackdropFilter` blurs arbitrary UIKit view hierarchies.
 * - Tier 3 (@shopify/react-native-skia): zero-dependency Skia fallback for iOS < 26, Android < 13,
 *   Expo Go, or web.
 */
export type GlassTier = 1 | 2 | 3;

const MIN_ANDROID_SHADER_API_LEVEL = 33;

let cachedTier: GlassTier | null = null;

function isNativeMaterialSupported(): boolean {
  // Tier 1: wraps the real OS UIVisualEffectView liquid glass material (iOS 26+, RN 0.80+).
  // `isLiquidGlassSupported` is a boolean constant, not a function — on iOS it is read from
  // the native module's constants at import time; on every other platform the package ships
  // a `false` stub, so this is safe to evaluate unconditionally.
  return isLiquidGlassSupported;
}

function parsePlatformMajorVersion(version: string | number): number {
  const parsed = typeof version === 'number' ? version : parseInt(version, 10);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function isNewArchitectureEnabled(): boolean {
  return Boolean((globalThis as { nativeFabricUIManager?: unknown }).nativeFabricUIManager);
}

function hasGpuShaderSupport(): boolean {
  // Tier 2: real-time AGSL RuntimeShader refraction on Android 13+ (API 33+) with New
  // Architecture enabled and a dev/release binary (no Expo Go) per react-native-glass.md §0 & §2.
  // iOS < 26 intentionally skips Tier 2 and falls through to Tier 3: the package's iOS Metal
  // implementation only samples UIImageView backdrops (>=15% window area) and renders nothing
  // over View/FlatList content, whereas Android's LiquidGlassView.kt falls back to bestBgView.
  if (!isNewArchitectureEnabled()) {
    return false;
  }

  if (Platform.OS !== 'android') {
    return false;
  }

  const apiLevel = parsePlatformMajorVersion(Platform.Version);
  if (apiLevel < MIN_ANDROID_SHADER_API_LEVEL) {
    return false;
  }

  // @uginy/react-native-liquid-glass registers an Expo module named 'LiquidGlass'.
  // In Expo Go or unlinked builds this returns null, falling through to Tier 3.
  return requireOptionalNativeModule('LiquidGlass') !== null;
}

function resolveGlassTier(): GlassTier {
  const nativeMaterial = isNativeMaterialSupported();
  const gpuShader = !nativeMaterial && hasGpuShaderSupport();
  const tier: GlassTier = nativeMaterial ? 1 : gpuShader ? 2 : 3;
  if (__DEV__) {
    // Which tier a build actually landed on is invisible from the UI alone — a Tier 1
    // surface over an opaque backdrop looks much like the Tier 3 fallback. Log it once so
    // "is the native material live?" is answerable without instrumenting a screen.
    // eslint-disable-next-line no-console
    console.log(
      `[useGlassTier] resolved Tier ${tier} (isLiquidGlassSupported=${nativeMaterial}, hasGpuShaderSupport=${gpuShader})`
    );
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
