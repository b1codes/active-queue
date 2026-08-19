import { __resetGlassTierCacheForTests, useGlassTier } from "../core/hooks/useGlassTier";

jest.mock("@callstack/liquid-glass", () => ({
  isLiquidGlassSupported: false,
}));

const liquidGlass = require("@callstack/liquid-glass") as { isLiquidGlassSupported: boolean };

describe("useGlassTier", () => {
  beforeEach(() => {
    __resetGlassTierCacheForTests();
    liquidGlass.isLiquidGlassSupported = false;
  });

  it("falls back to Tier 3 when the native liquid glass material is unavailable", () => {
    expect(useGlassTier()).toBe(3);
  });

  it("resolves to Tier 1 when @callstack/liquid-glass reports native material support", () => {
    liquidGlass.isLiquidGlassSupported = true;
    expect(useGlassTier()).toBe(1);
  });

  it("caches the resolved tier across calls instead of re-resolving per render", () => {
    const first = useGlassTier();
    liquidGlass.isLiquidGlassSupported = true;
    const second = useGlassTier();
    expect(second).toBe(first);
  });
});
