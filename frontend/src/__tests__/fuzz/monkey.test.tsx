/**
 * Seeded monkey runs over every screen against the stateful fake API (see
 * src/test-utils/monkey.tsx for what fails a run).
 *
 * PR runs use fixed seeds, so they are reproducible and a red run is a real regression.
 * The nightly job (fuzz-nightly.yml) sets MONKEY_SEED to a fresh, logged seed and raises
 * MONKEY_RUNS / MONKEY_STEPS. Replay any failure with the seed from its message:
 *
 *   MONKEY_SEED=<seed> pnpm test -- monkey
 */
import { Linking } from 'react-native';
import { resetRouter } from '@/test-utils/router';
import { resetStores } from '@/test-utils';
import { runMonkey } from '@/test-utils/monkey';
import QueueScreen from '@app/(app)/index';
import BlocksScreen from '@app/(app)/blocks';
import HistoryScreen from '@app/(app)/history';
import MatchScreen from '@app/(app)/match/[contentId]';
import SessionScreen from '@app/(app)/session/[id]';
import SettingsScreen from '@app/(app)/settings';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

const SCREENS = {
  '/(app)': QueueScreen,
  '/(app)/blocks': BlocksScreen,
  '/(app)/history': HistoryScreen,
  '/(app)/settings': SettingsScreen,
  '/(app)/match/[contentId]': MatchScreen,
  '/(app)/session/[id]': SessionScreen,
};

const STARTS: { path: string; params: Record<string, string> }[] = [
  { path: '/(app)', params: {} },
  { path: '/(app)/blocks', params: {} },
  { path: '/(app)/history', params: {} },
  { path: '/(app)/settings', params: {} },
  { path: '/(app)/match/[contentId]', params: { contentId: 'fx:fx_vid_3' } },
];

const envSeed = process.env.MONKEY_SEED ? Number(process.env.MONKEY_SEED) : null;
const RUNS = Number(process.env.MONKEY_RUNS ?? 3);
const STEPS = Number(process.env.MONKEY_STEPS ?? 60);
// Fixed PR seeds; the nightly derives its runs from one logged seed.
const seeds = Array.from({ length: RUNS }, (_, i) => (envSeed ?? 20261110) + i * 7919);

beforeEach(() => {
  resetStores();
  resetRouter();
  jest.spyOn(Linking, 'canOpenURL').mockResolvedValue(true);
  jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
});

describe.each(STARTS)('monkey from $path', (start) => {
  it.each(seeds)('seed %i, healthy API', (seed) => runMonkey({ seed, steps: STEPS, screens: SCREENS, start }));

  it.each(seeds)('seed %i, flaky API (15% of requests fail)', (seed) =>
    runMonkey({ seed, steps: STEPS, screens: SCREENS, start, failureRate: 0.15 })
  );
});
