/**
 * Renders every Storybook story and runs the accessibility audit over it.
 *
 * The stories already enumerate each component's meaningful states (loading, error,
 * matched, disabled...), so sweeping them audits every state without restating fixtures here.
 * A new story is picked up automatically.
 */
import fs from 'fs';
import path from 'path';
import React from 'react';
import { act } from '@testing-library/react-native';
import { renderWithProviders, resetStores } from '@/test-utils';
import { expectAccessible } from '@/test-utils/a11y';

// storybook/test ships ESM only; stories just need its `fn()` spy factory.
jest.mock('storybook/test', () => ({ fn: (impl?: (...a: unknown[]) => unknown) => jest.fn(impl) }));

interface StoryModule {
  default: {
    title: string;
    component?: React.ComponentType<Record<string, unknown>>;
    args?: Record<string, unknown>;
    render?: (args: Record<string, unknown>) => React.ReactElement;
  };
  [name: string]: unknown;
}

interface Story {
  args?: Record<string, unknown>;
  render?: (args: Record<string, unknown>) => React.ReactElement;
}

function storyFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return storyFiles(full);
    return e.name.endsWith('.stories.tsx') ? [full] : [];
  });
}

const SRC = path.resolve(__dirname, '../..');
const cases = storyFiles(SRC).flatMap((file) => {
  const mod = require(file) as StoryModule;
  const meta = mod.default;
  return Object.entries(mod)
    .filter(([name, value]) => name !== 'default' && typeof value === 'object' && value !== null)
    .map(([name, value]) => ({ id: `${meta.title} / ${name}`, meta, story: value as Story }));
});

beforeEach(() => resetStores());

it('finds the stories', () => {
  expect(cases.length).toBeGreaterThanOrEqual(16);
});

describe.each(cases)('$id', ({ meta, story }) => {
  it('has no accessibility violations', async () => {
    const args = { ...meta.args, ...story.args };
    const render = story.render ?? meta.render;
    const Component = meta.component;
    const ui = render ? render(args) : Component ? <Component {...args} /> : null;
    if (!ui) throw new Error('story has neither render nor component');
    await renderWithProviders(ui);
    await act(async () => {});
    expectAccessible();
  });
});
