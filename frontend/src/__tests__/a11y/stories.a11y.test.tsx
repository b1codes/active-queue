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
import { collectStories, type StoryModule } from '../../../.rnstorybook/screenshots/catalog';

// storybook/test ships ESM only; stories just need its `fn()` spy factory.
jest.mock('storybook/test', () => ({ fn: (impl?: (...a: unknown[]) => unknown) => jest.fn(impl) }));

function storyModules(dir: string): StoryModule[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return storyModules(full);
    return e.name.endsWith('.stories.tsx') ? [require(full) as StoryModule] : [];
  });
}

// The screenshot harness's catalog renders each story the way Storybook does, inside its
// own and its meta's decorators (LiquidGlassSurface's swatch backdrop is one), so the
// contrast check sees the same background a viewer would.
const SRC = path.resolve(__dirname, '../..');
const cases = collectStories(storyModules(SRC), 'file:///thumb.png');

beforeEach(() => resetStores());

it('finds the stories', () => {
  expect(cases.length).toBeGreaterThanOrEqual(16);
});

describe.each(cases)('$title $exportName', ({ Component }) => {
  it('has no accessibility violations', async () => {
    await renderWithProviders(<Component />);
    await act(async () => {});
    expectAccessible();
  });
});
