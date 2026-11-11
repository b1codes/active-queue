/**
 * Render budgets (ClickUp 86bcxrv0j). Jest can't measure frame rate, but it can count the
 * work that costs frames: how many rows a long feed mounts, which components re-render when
 * state changes, and whether anything animates on the JS thread. These are deterministic,
 * so they gate every PR. Frame rate and startup on a device are in docs/manual-qa.md.
 *
 * The 2-layer GPU blur budget is checked in every test, not just here (jest.setup.ts).
 */
import fs from 'fs';
import path from 'path';
import React from 'react';
import { AppState } from 'react-native';
import { act, screen } from '@testing-library/react-native';
import { resetRouter } from '@/test-utils/router';
import { feedItem, mockApi, renderWithProviders, resetStores, source } from '@/test-utils';
import { useQueueStore } from '@/features/queue/queueStore';
import { store } from '@/store';
import { setSyncProgress } from '@/features/queue/queueSlice';
import QueueScreen from '@app/(app)/index';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

// Count FeedCard renders while keeping its memo comparison, so a parent that passes new
// props on every render (a fresh onPress arrow, say) shows up as renders.
const mockRenders = { feedCard: 0 };
jest.mock('@/features/queue/components/FeedCard', () => {
  const actual = jest.requireActual('@/features/queue/components/FeedCard');
  const mockReact = jest.requireActual('react');
  const Inner = actual.FeedCard.type;
  const Counted = (props: object) => {
    mockRenders.feedCard += 1;
    return mockReact.createElement(Inner, props);
  };
  return { ...actual, FeedCard: mockReact.memo(Counted, actual.FeedCard.compare ?? undefined) };
});

const LONG_FEED = 1000;
// Rows a feed may mount before the user scrolls: about two screens of cards.
const FIRST_WINDOW = 20;

function feedRoutes(items: number) {
  return {
    'GET /api/v1/content/feed': {
      data: { items: [...Array(items)].map((_, i) => feedItem(i + 1)), next_cursor: null, total_unconsumed: items },
    },
    'GET /api/v1/sources': { data: { items: [source({ item_count: items })] } },
    'GET /api/v1/sessions/active': { data: null },
  } as Parameters<typeof mockApi>[0];
}

beforeEach(() => {
  resetStores();
  resetRouter();
  mockRenders.feedCard = 0;
  jest.spyOn(AppState, 'addEventListener').mockImplementation((() => ({ remove: jest.fn() })) as never);
});

async function mountLongFeed() {
  mockApi(feedRoutes(LONG_FEED));
  await renderWithProviders(<QueueScreen />);
  await screen.findByText('Fixture Workout Video #1');
  await act(async () => {});
}

describe('a long feed', () => {
  it('mounts only the first window of rows, not every item', async () => {
    await mountLongFeed();
    // FlatList mounts initialNumToRender rows (8) and grows in batches as the user scrolls.
    // A ScrollView over .map(), or a much larger first window, mounts far more here.
    expect(screen.queryAllByText(/^Fixture Workout Video #/).length).toBeLessThanOrEqual(FIRST_WINDOW);
    expect(mockRenders.feedCard).toBeLessThanOrEqual(FIRST_WINDOW);
  });

  it('re-renders no row when sync progress ticks', async () => {
    // A 5,000-item sync dispatches progress 20 times while the feed is on screen.
    await mountLongFeed();
    useQueueStore.setState({
      syncProgress: { ...store.getState().queue.syncProgress, isSyncing: true, sourceId: 'u1_fixture_pl' },
    });
    await act(async () => {});
    const before = mockRenders.feedCard;
    for (let chunk = 1; chunk <= 20; chunk++) {
      await act(async () => {
        store.dispatch(setSyncProgress({ itemsSyncedTotal: chunk * 250, iterationCount: chunk }));
      });
    }
    expect(mockRenders.feedCard - before).toBe(0);
  });

  it('re-renders no row when a banner or error changes above it', async () => {
    await mountLongFeed();
    const before = mockRenders.feedCard;
    await act(async () => {
      useQueueStore.setState({ feedError: { code: 'NETWORK_UNAVAILABLE', message: 'offline' } as never });
    });
    await act(async () => {
      useQueueStore.setState({ feedError: null, totalUnconsumed: LONG_FEED - 1 });
    });
    expect(mockRenders.feedCard - before).toBe(0);
  });
});

describe('animation', () => {
  // Every animation must run on the UI thread (Reanimated worklets). Anything that ticks
  // React state per frame, or core Animated without the native driver, competes with
  // scrolling and taps on the JS thread.
  const walk = (dir: string): string[] =>
    fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) return e.name === '__tests__' || e.name === 'test-utils' ? [] : walk(p);
      return /\.(tsx?|jsx?)$/.test(e.name) && !/\.stories\./.test(e.name) ? [p] : [];
    });
  const files = ['src', 'app'].flatMap((d) => walk(path.join(__dirname, '..', '..', '..', d)));

  it('found the source files', () => {
    expect(files.length).toBeGreaterThan(40);
  });

  it.each([
    ['requestAnimationFrame', /\brequestAnimationFrame\s*\(/],
    ['setInterval', /\bsetInterval\s*\(/],
    ["react-native's Animated", /\bAnimated\.(timing|spring|decay|loop|sequence|parallel)\s*\(/],
    ['LayoutAnimation', /\bLayoutAnimation\./],
  ])('nothing animates with %s', (_name, pattern) => {
    const offenders = files.filter((f) => pattern.test(fs.readFileSync(f, 'utf8')));
    expect(offenders.map((f) => path.relative(process.cwd(), f))).toEqual([]);
  });
});
