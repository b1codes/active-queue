/**
 * GPU overdraw guardrail (gpu-acceleration.md): at most 2 concurrent blur/backdrop-filter
 * layers app-wide, counted per mounted LiquidGlassSurface regardless of tier.
 *
 * In development a 3rd concurrent layer warns. In Jest, jest.setup.ts fails any test whose
 * peak went over the budget, so every story, screen state and monkey walk is checked.
 */
export const GPU_BLUR_LAYER_BUDGET = 2;

let active = 0;
let peak = 0;

/** Call when a glass layer mounts; returns the release to call when it unmounts. */
export function acquireGlassLayer(): () => void {
  active += 1;
  peak = Math.max(peak, active);
  if (active > GPU_BLUR_LAYER_BUDGET) {
    console.warn(
      `[LiquidGlassSurface] ${active} concurrent glass layers mounted — exceeds the ` +
        `${GPU_BLUR_LAYER_BUDGET}-layer GPU guardrail (gpu-acceleration.md). Use a ` +
        'pre-rendered translucent color for secondary surfaces instead of another live blur.'
    );
  }
  let released = false;
  return () => {
    if (released) return;
    released = true;
    active -= 1;
  };
}

/** The most glass layers mounted at once since the last reset. */
export function glassLayerPeak(): number {
  return peak;
}

/** Start a new measurement from what is mounted now. */
export function resetGlassLayerPeak(): void {
  peak = active;
}
