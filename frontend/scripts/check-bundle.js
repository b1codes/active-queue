#!/usr/bin/env node
/**
 * Startup budget for the production iOS bundle (ClickUp 86bcxrv0j).
 *
 * Hermes loads and maps the whole bytecode bundle at launch, so its size is the part of
 * startup time a code change controls, and it is deterministic enough to gate every PR.
 * Fails when the bundle grows past BUDGET_BYTES, or contains Storybook (on-device
 * Storybook adds ~2.9 MiB, +51%, and must only ship with STORYBOOK_ENABLED=true).
 *
 *   npx expo export --platform ios --output-dir dist-ios
 *   node scripts/check-bundle.js dist-ios
 *
 * Raise the budget only for a reason you would defend in review, and note it here.
 * 2026-11: 5.70 MiB.
 */
const fs = require('fs');
const path = require('path');

const BUDGET_BYTES = 6.5 * 1024 * 1024; // 6.5 MiB
const FORBIDDEN = [
  ['Storybook', /storybook/i],
  ['test utilities', /mockApi: unexpected request|installFakeBackend/],
];

const dir = process.argv[2] || 'dist-ios';
const bundleDir = path.join(dir, '_expo', 'static', 'js', 'ios');
const bundles = fs.existsSync(bundleDir) ? fs.readdirSync(bundleDir).filter((f) => f.endsWith('.hbc')) : [];
if (bundles.length !== 1) {
  console.error(`check-bundle: expected one .hbc bundle in ${bundleDir}, found ${bundles.length}`);
  process.exit(1);
}

const file = path.join(bundleDir, bundles[0]);
const bytes = fs.readFileSync(file);
const text = bytes.toString('latin1');
const mb = (n) => `${(n / 1024 / 1024).toFixed(2)} MiB`;
const problems = [];
if (bytes.length > BUDGET_BYTES) {
  problems.push(`the bundle is ${mb(bytes.length)}, over the ${mb(BUDGET_BYTES)} budget`);
}
for (const [name, pattern] of FORBIDDEN) {
  if (pattern.test(text)) problems.push(`the production bundle contains ${name}`);
}

console.log(`check-bundle: ${bundles[0]} is ${mb(bytes.length)} (budget ${mb(BUDGET_BYTES)})`);
if (problems.length) {
  for (const p of problems) console.error(`check-bundle: ${p}`);
  process.exit(1);
}
