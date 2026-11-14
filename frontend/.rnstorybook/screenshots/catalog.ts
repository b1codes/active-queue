/**
 * Pure helpers for the visual-regression harness (ClickUp 86bcxruz4). Kept free of React
 * Native imports so Jest can hold them to the same story list the capture script uses.
 */
import React from 'react';

/** The glass tiers the harness captures. Tier 2 never resolves (see useGlassTier). */
export type CaptureTier = 1 | 3;

export interface HarnessTarget {
  storyId: string;
  tier: CaptureTier;
}

/** Storybook's decorator shape: wraps the story it's given. */
export type StoryDecorator = (Story: React.ComponentType, context: unknown) => React.ReactElement;

export interface StoryModule {
  default: {
    title: string;
    component?: React.ComponentType<Record<string, unknown>>;
    args?: Record<string, unknown>;
    render?: (args: Record<string, unknown>) => React.ReactElement;
    decorators?: StoryDecorator[];
  };
  [exportName: string]: unknown;
}

interface StoryExport {
  args?: Record<string, unknown>;
  render?: (args: Record<string, unknown>) => React.ReactElement;
  decorators?: StoryDecorator[];
}

/**
 * Wraps `Inner` in `decorators` the way Storybook does: the first decorator in the list
 * sits closest to the story.
 */
export function decorate(Inner: React.ComponentType, decorators: StoryDecorator[]): React.ComponentType {
  return decorators.reduce<React.ComponentType>((Wrapped, decorator) => {
    const Decorated = () => decorator(Wrapped, {});
    return Decorated;
  }, Inner);
}

export interface CatalogEntry {
  id: string;
  title: string;
  exportName: string;
  /**
   * Renders the story the way Storybook does: meta args, then story args, then render,
   * inside the story's decorators, then the meta's. preview.tsx's go on outside these.
   */
  Component: React.ComponentType;
}

/**
 * `Core/GlassHeader` + `WithSubtitle` -> `core-glassheader--with-subtitle`. Must match
 * scripts/screenshots/storyList.js, which derives the same IDs from the source files.
 */
export function storyId(title: string, exportName: string): string {
  const slug = (s: string) =>
    s
      .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  return `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')}--${slug(exportName)}`;
}

const REMOTE_IMAGE = /^https?:\/\/[^\s]+\.(?:jpe?g|png|webp)(?:\?[^\s]*)?$/i;

/**
 * Swaps every remote image URL in a story's args for `localUri`, so a capture never
 * depends on the network or on what a CDN serves today. Functions, React elements and
 * non-image strings pass through untouched.
 */
export function localizeImages<T>(value: T, localUri: string): T {
  if (typeof value === 'string') {
    return (REMOTE_IMAGE.test(value) ? localUri : value) as T;
  }
  if (Array.isArray(value)) {
    return value.map((v) => localizeImages(v, localUri)) as T;
  }
  if (value && typeof value === 'object' && !React.isValidElement(value)) {
    const proto = Object.getPrototypeOf(value);
    if (proto !== Object.prototype && proto !== null) return value;
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, localizeImages(v, localUri)]),
    ) as T;
  }
  return value;
}

/** Flattens story modules into entries sorted by ID. Throws on a duplicate ID. */
export function collectStories(modules: StoryModule[], localUri: string): CatalogEntry[] {
  const entries = modules.flatMap((mod) => {
    const meta = mod.default;
    return Object.entries(mod)
      .filter(([name, value]) => name !== 'default' && typeof value === 'object' && value !== null)
      .map(([exportName, value]) => {
        const story = value as StoryExport;
        const args = localizeImages({ ...meta.args, ...story.args }, localUri);
        const render = story.render ?? meta.render;
        const Inner = meta.component;
        if (!render && !Inner) {
          throw new Error(`${meta.title}/${exportName}: story has neither render nor component`);
        }
        // A function component, so hooks inside a story's render() run as they do in
        // Storybook.
        const Bare = () => (render ? render(args) : Inner ? React.createElement(Inner, args) : null);
        const Component = decorate(Bare, [...(story.decorators ?? []), ...(meta.decorators ?? [])]);
        Component.displayName = `Story(${meta.title}/${exportName})`;
        return { id: storyId(meta.title, exportName), title: meta.title, exportName, Component };
      });
  });
  const seen = new Set<string>();
  for (const e of entries) {
    if (seen.has(e.id)) throw new Error(`duplicate story ID ${e.id}`);
    seen.add(e.id);
  }
  return entries.sort((a, b) => a.id.localeCompare(b.id));
}

/**
 * The capture script launches the harness with `-vrStory <id> -vrTier <1|3>`. iOS puts
 * launch arguments in NSUserDefaults, which React Native's Settings reads. Returns null
 * when the arguments are malformed, which the harness renders as an error screen.
 */
export function parseHarnessArgs(story: unknown, tier: unknown): HarnessTarget | null {
  const id = typeof story === 'string' ? story : '';
  const t = String(tier);
  if (!/^[a-z0-9-]+$/.test(id) || (t !== '1' && t !== '3')) return null;
  return { storyId: id, tier: Number(t) as CaptureTier };
}

/** 2026-11-03 09:41 UTC: every capture renders as if it were this instant. */
export const FROZEN_NOW = Date.UTC(2026, 10, 3, 9, 41, 0);

/**
 * Replaces the global Date so `new Date()` and `Date.now()` return `now`. Dates built from
 * explicit values are unaffected, and timers keep running (they don't read Date).
 */
export function freezeClock(now: number = FROZEN_NOW): DateConstructor {
  const RealDate = Date;
  const Frozen = new Proxy(RealDate, {
    construct(target, args: unknown[]) {
      return args.length === 0 ? new target(now) : Reflect.construct(target, args);
    },
    get(target, prop, receiver) {
      if (prop === 'now') return () => now;
      return Reflect.get(target, prop, receiver);
    },
  });
  globalThis.Date = Frozen;
  return RealDate;
}
