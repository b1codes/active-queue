import { Platform } from "react-native";
import { __resetGlassTierCacheForTests, useGlassTier } from "../core/hooks/useGlassTier";

jest.mock("@callstack/liquid-glass", () => ({
  isLiquidGlassSupported: false,
}));

const mockRequireOptionalNativeModule = jest.fn<unknown, [string]>(() => null);

jest.mock("expo", () => ({
  requireOptionalNativeModule: (name: string) => mockRequireOptionalNativeModule(name),
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const liquidGlass = require("@callstack/liquid-glass") as { isLiquidGlassSupported: boolean };

const globalWithFabric = globalThis as { nativeFabricUIManager?: unknown };

function setPlatform(os: "ios" | "android" | "web", version: string | number) {
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
    mockRequireOptionalNativeModule.mockReset();
    mockRequireOptionalNativeModule.mockReturnValue(null);
    delete globalWithFabric.nativeFabricUIManager;
    setPlatform("ios", "18.6");
  });

  afterAll(() => {
    setPlatform(originalOS as "ios" | "android" | "web", originalVersion);
    if (originalFabric === undefined) {
      delete globalWithFabric.nativeFabricUIManager;
    } else {
      globalWithFabric.nativeFabricUIManager = originalFabric;
    }
  });

  it("falls back to Tier 3 when neither Tier 1 nor Tier 2 is available", () => {
    expect(useGlassTier()).toBe(3);
  });

  it("resolves to Tier 1 when @callstack/liquid-glass reports native material support", () => {
    liquidGlass.isLiquidGlassSupported = true;
    expect(useGlassTier()).toBe(1);
  });

  it("prefers Tier 1 over Tier 2 when both native material and GPU shader are available", () => {
    liquidGlass.isLiquidGlassSupported = true;
    globalWithFabric.nativeFabricUIManager = {};
    mockRequireOptionalNativeModule.mockReturnValue({});
    setPlatform("ios", "26.2");

    expect(useGlassTier()).toBe(1);
  });

  it("resolves to Tier 2 on Android 13+ (API 33+) with New Architecture and linked LiquidGlass module", () => {
    globalWithFabric.nativeFabricUIManager = {};
    mockRequireOptionalNativeModule.mockImplementation((name) =>
      name === "LiquidGlass" ? {} : null
    );
    setPlatform("android", 33);

    expect(useGlassTier()).toBe(2);
  });

  it("falls back to Tier 3 on iOS 15–25 so non-image View/FlatList backdrops blur via Skia", () => {
    globalWithFabric.nativeFabricUIManager = {};
    mockRequireOptionalNativeModule.mockImplementation((name) =>
      name === "LiquidGlass" ? {} : null
    );
    setPlatform("ios", "18.6");

    expect(useGlassTier()).toBe(3);
  });

  it("falls back to Tier 3 when New Architecture (Fabric) is disabled", () => {
    delete globalWithFabric.nativeFabricUIManager;
    mockRequireOptionalNativeModule.mockReturnValue({});
    setPlatform("android", 34);

    expect(useGlassTier()).toBe(3);
  });

  it("falls back to Tier 3 below the Android OS version floor (API < 33)", () => {
    globalWithFabric.nativeFabricUIManager = {};
    mockRequireOptionalNativeModule.mockReturnValue({});

    setPlatform("android", 32);
    expect(useGlassTier()).toBe(3);
  });

  it("falls back to Tier 3 in Expo Go when the native LiquidGlass module is not linked", () => {
    globalWithFabric.nativeFabricUIManager = {};
    mockRequireOptionalNativeModule.mockReturnValue(null);
    setPlatform("android", 34);

    expect(useGlassTier()).toBe(3);
  });

  it("caches the resolved tier across calls instead of re-resolving per render", () => {
    const first = useGlassTier();
    liquidGlass.isLiquidGlassSupported = true;
    const second = useGlassTier();
    expect(second).toBe(first);
  });
});
