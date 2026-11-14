/**
 * The visual-regression harness (.rnstorybook/screenshots) and the capture script
 * (scripts/screenshots) must agree on which stories exist and what they're called. The
 * script reads IDs from source and the harness from the real modules, so this test is
 * what stops a story from going uncaptured, or a capture from landing on the harness's
 * "unknown story" screen.
 */
import fs from 'fs';
import path from 'path';
import React from 'react';
import { act, render, screen } from '@testing-library/react-native';
import type { TestInstance } from 'test-renderer';
import { renderWithProviders, resetStores } from '@/test-utils';
import {
  collectStories,
  decorate,
  freezeClock,
  FROZEN_NOW,
  localizeImages,
  parseHarnessArgs,
  storyId,
  type StoryModule,
} from '../../../.rnstorybook/screenshots/catalog';

jest.mock('storybook/test', () => ({ fn: (impl?: (...a: unknown[]) => unknown) => jest.fn(impl) }));

const { storyIds } = require('../../../scripts/screenshots/storyList') as {
  storyIds: (dir?: string) => string[];
};

function storyModules(dir: string): StoryModule[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === '__tests__' ? [] : storyModules(full);
    return e.name.endsWith('.stories.tsx') ? [require(full) as StoryModule] : [];
  });
}

const SRC = path.resolve(__dirname, '../..');

describe('story catalog', () => {
  const catalog = collectStories(storyModules(SRC), 'file:///thumb.png');

  it('matches the IDs the capture script reads from source', () => {
    expect(catalog.map((e) => e.id)).toEqual(storyIds());
    expect(catalog.length).toBeGreaterThanOrEqual(49);
  });

  it('has a baseline for every story on both tiers, and none for a removed story', () => {
    const baselines = path.resolve(__dirname, '../../../screenshots/baselines');
    for (const tier of ['tier1', 'tier3']) {
      const dir = path.join(baselines, tier);
      const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith('.png')) : [];
      expect(files.map((f) => f.replace(/\.png$/, '')).sort()).toEqual(catalog.map((e) => e.id));
    }
  });

  async function imageUris(entry: (typeof catalog)[number]): Promise<string[]> {
    resetStores();
    await renderWithProviders(<entry.Component />);
    await act(async () => {});
    const uris: string[] = [];
    const walk = (n: TestInstance) => {
      // RN's Image hands native an array of sources.
      for (const src of [n.props.source].flat() as ({ uri?: unknown } | undefined)[]) {
        if (typeof src?.uri === 'string') uris.push(src.uri);
      }
      n.children.forEach((c) => typeof c !== 'string' && walk(c));
    };
    if (screen.root) walk(screen.root);
    return uris;
  }

  it.each(catalog.map((e) => [e.id, e] as const))('%s loads no remote image', async (_id, entry) => {
    expect((await imageUris(entry)).filter((u) => /^https?:/.test(u))).toEqual([]);
  });

  it('swaps the FeedCard thumbnail for the bundled file', async () => {
    const feedCard = catalog.find((e) => e.id === 'queue-feedcard--default')!;
    expect(await imageUris(feedCard)).toEqual(['file:///thumb.png']);
  });

  it("renders a story inside its own and its meta's decorators", async () => {
    // LiquidGlassSurface's meta decorator paints the swatches the glass sits over.
    const glass = catalog.find((e) => e.id === 'core-liquidglasssurface--default')!;
    await renderWithProviders(<glass.Component />);
    const fills = new Set<string>();
    const walk = (n: TestInstance) => {
      const bg = [n.props.style].flat(Infinity).find((st) => st && (st as { backgroundColor?: string }).backgroundColor);
      if (bg) fills.add((bg as { backgroundColor: string }).backgroundColor);
      n.children.forEach((c) => typeof c !== 'string' && walk(c));
    };
    if (screen.root) walk(screen.root);
    expect([...fills]).toEqual(expect.arrayContaining(['#FF3B30', '#FF9500', '#41D2B3', '#65201E']));
  });

  it('rejects duplicate IDs and stories with nothing to render', () => {
    const mod = { default: { title: 'A/B', component: () => null }, X: {} } as unknown as StoryModule;
    expect(() => collectStories([mod, mod], 'u')).toThrow('duplicate story ID a-b--x');
    const empty = { default: { title: 'A/C' }, X: {} } as unknown as StoryModule;
    expect(() => collectStories([empty], 'u')).toThrow('neither render nor component');
  });
});

describe('decorate', () => {
  it('puts the first decorator closest to the story, as Storybook does', async () => {
    const order: string[] = [];
    const wrap = (name: string) =>
      function Wrap(Story: React.ComponentType) {
        order.push(name);
        return <Story />;
      };
    const Story = decorate(() => {
      order.push('story');
      return null;
    }, [wrap('story-level'), wrap('meta-level'), wrap('global')]);
    await render(<Story />);
    expect(order).toEqual(['global', 'meta-level', 'story-level', 'story']);
  });
});

describe('storyId', () => {
  it.each([
    ['Core/GlassHeader', 'WithSubtitle', 'core-glassheader--with-subtitle'],
    ['States/DeepLinkFailedCard', 'YouTube', 'states-deeplinkfailedcard--you-tube'],
    ['Queue/FeedCard', 'Default', 'queue-feedcard--default'],
  ])('%s %s -> %s', (title, name, id) => {
    expect(storyId(title, name)).toBe(id);
  });
});

describe('parseHarnessArgs', () => {
  it('reads the story and tier, as strings or numbers', () => {
    expect(parseHarnessArgs('queue-feedcard--default', '1')).toEqual({ storyId: 'queue-feedcard--default', tier: 1 });
    expect(parseHarnessArgs('queue-feedcard--default', 3)).toEqual({ storyId: 'queue-feedcard--default', tier: 3 });
  });

  it.each([
    ['queue-feedcard--default', undefined],
    ['queue-feedcard--default', '2'],
    ['Queue FeedCard', '3'],
    ['', '3'],
    [42, '3'],
  ])('rejects %p tier %p', (story, tier) => {
    expect(parseHarnessArgs(story, tier)).toBeNull();
  });
});

describe('localizeImages', () => {
  it('replaces remote image URLs at any depth and keeps everything else', () => {
    const onPress = jest.fn();
    const el = <></>;
    const args = {
      item: { thumbnail_url: 'https://i.ytimg.com/vi/x/hqdefault.jpg?v=2', video_url: 'https://youtube.com/watch?v=x' },
      list: ['http://cdn.example/a.PNG', 'plain'],
      onPress,
      el,
      when: new Date(0),
    };
    const out = localizeImages(args, 'file:///local.png');
    expect(out.item).toEqual({ thumbnail_url: 'file:///local.png', video_url: 'https://youtube.com/watch?v=x' });
    expect(out.list).toEqual(['file:///local.png', 'plain']);
    expect(out.onPress).toBe(onPress);
    expect(out.el).toBe(el);
    expect(out.when).toBe(args.when);
  });
});

describe('freezeClock', () => {
  it('pins now and leaves explicit dates alone', () => {
    const RealDate = freezeClock();
    try {
      expect(Date.now()).toBe(FROZEN_NOW);
      expect(new Date().toISOString()).toBe('2026-11-03T09:41:00.000Z');
      expect(new Date(0).getTime()).toBe(0);
      expect(new Date(2020, 0, 2).getFullYear()).toBe(2020);
      expect(new Date() instanceof RealDate).toBe(true);
    } finally {
      globalThis.Date = RealDate;
    }
  });
});
