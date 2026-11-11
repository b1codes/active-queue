/**
 * Story IDs for the screenshot run, read from the story files' source without bundling
 * them. Jest (src/__tests__/visual/catalog.test.ts) holds this list to the IDs the harness
 * derives from the real modules, so the two can't drift.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '../../src');

function storyFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === '__tests__' ? [] : storyFiles(full);
    return e.name.endsWith('.stories.tsx') ? [full] : [];
  });
}

/** Same rule as storyId() in .rnstorybook/screenshots/catalog.ts. */
function storyId(title, exportName) {
  const titleSlug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  const nameSlug = exportName
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `${titleSlug}--${nameSlug}`;
}

function storyIds(srcDir = SRC) {
  return storyFiles(srcDir)
    .flatMap((file) => {
      const source = fs.readFileSync(file, 'utf8');
      // The meta object's title: the first `title:` after `const meta =`.
      const metaAt = source.indexOf('const meta');
      const title = /title:\s*['"]([^'"]+)['"]/.exec(source.slice(metaAt));
      if (metaAt < 0 || !title) throw new Error(`${file}: no meta title`);
      const exports = [...source.matchAll(/^export const (\w+)/gm)].map((m) => m[1]);
      return exports.map((name) => storyId(title[1], name));
    })
    .sort((a, b) => a.localeCompare(b));
}

module.exports = { storyIds, storyId };

if (require.main === module) {
  for (const id of storyIds()) console.log(id);
}
