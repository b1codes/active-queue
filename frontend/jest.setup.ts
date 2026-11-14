/* Global Jest setup: native-module mocks so components and screens render in Node. */
import 'react-native-gesture-handler/jestSetup';
import { GPU_BLUR_LAYER_BUDGET, glassLayerPeak, resetGlassLayerPeak } from './src/core/perf/glassBudget';

// Reanimated's mock omits useReducedMotion ("ADD ME IF NEEDED"); ChromaticPulse needs it.
jest.mock('react-native-reanimated', () => ({
  ...require('react-native-reanimated/mock'),
  useReducedMotion: jest.fn(() => false),
}));

// AsyncStorage's own Jest mock (used by Firebase Auth persistence wiring).
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

// Silence the dev-only glass tier log line in test output.
const originalLog = console.log;
beforeAll(() => {
  console.log = (...args: unknown[]) => {
    if (typeof args[0] === 'string' && args[0].startsWith('[useGlassTier]')) return;
    originalLog(...args);
  };
});
afterAll(() => {
  console.log = originalLog;
});

// GPU blur budget (src/core/perf/glassBudget.ts): no test may mount more than 2 glass layers
// at once. Every story, screen state and monkey walk therefore checks it.
beforeEach(() => resetGlassLayerPeak());
afterEach(() => {
  const peak = glassLayerPeak();
  if (peak > GPU_BLUR_LAYER_BUDGET) {
    throw new Error(
      `${peak} glass layers were mounted at once; the GPU budget is ${GPU_BLUR_LAYER_BUDGET} ` +
        '(src/core/perf/glassBudget.ts). Use a pre-rendered translucent color for secondary surfaces.'
    );
  }
});
