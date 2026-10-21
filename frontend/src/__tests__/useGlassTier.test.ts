import { Platform } from "react-native";
import { __resetGlassTierCacheForTests, useGlassTier } from "../core/hooks/useGlassTier";

jest.mock("@callstack/liquid-glass", () => ({
  isLiquidGlassSupported: false,
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const liquidGlass = require("@callstack/liquid-glass") as { isLiquidGlassSupported: boolean };

const globalWithFabric = globalThis as { nativeFabricUIManager?: unknown };

function setPlatform(os: "ios" | "android", version: string | number) {
  Object.defineProperty(Platform, "OS", { configurable: true, value: os });
  Object.defineProperty(Platform, "Version", { configurable: true, value: version });
}

describe("useGlassTier", () => {
  const originalOS = Platform.OS;
  const originalVersion = Platform.Version;
  const originalFabric = globalWithFabric.nativeFabricUIManager;

  beforeEach(() => {
    __resetGlassTierCacheForTests();
    liquidGlass.isLiquidGlassSupported = false;
  });

  afterAll(() => {
    setPlatform(originalOS as "ios" | "android", originalVersion);
    globalWithFabric.nativeFabricUIManager = originalFabric;
  });

  it("falls back to Tier 3 when the native liquid glass material is unavailable", () => {
    expect(useGlassTier()).toBe(3);
  });

  it("resolves to Tier 1 when @callstack/liquid-glass reports native material support", () => {
    liquidGlass.isLiquidGlassSupported = true;
    expect(useGlassTier()).toBe(1);
  });

  // Tier 2 (@uginy/react-native-liquid-glass) was rejected on both platforms — guard against
  // it being re-enabled on the runtimes it was evaluated on without revisiting that decision.
  it("resolves to Tier 3, not Tier 2, on Android 13+ with New Architecture", () => {
    globalWithFabric.nativeFabricUIManager = {};
    setPlatform("android", 34);
    expect(useGlassTier()).toBe(3);
  });

  it("resolves to Tier 3, not Tier 2, on iOS below 26", () => {
    globalWithFabric.nativeFabricUIManager = {};
    setPlatform("ios", "18.6");
    expect(useGlassTier()).toBe(3);
  });

  it("caches the resolved tier across calls instead of re-resolving per render", () => {
    const first = useGlassTier();
    liquidGlass.isLiquidGlassSupported = true;
    const second = useGlassTier();
    expect(second).toBe(first);
  });
});
