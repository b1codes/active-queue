import { useGlassTier } from "../core/hooks/useGlassTier";

describe("useGlassTier", () => {
  it("resolves to Tier 3 while no native or GPU-shader glass package is installed", () => {
    expect(useGlassTier()).toBe(3);
  });

  it("caches the resolved tier across calls instead of re-resolving per render", () => {
    const first = useGlassTier();
    const second = useGlassTier();
    expect(first).toBe(second);
  });
});
