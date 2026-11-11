#!/usr/bin/env node
/**
 * Screenshot tests for every Storybook story, on both glass tiers (ClickUp 86bcxruz4).
 * See docs/testing.md#visual-regression-tests.
 *
 *   node scripts/screenshots/capture.js [--update] [--only <substring>] [--app <path>]
 *                                       [--off-reference] [--baselines <dir>]
 *
 * Boots a fresh simulator of the reference model and OS (screenshots/reference.json),
 * installs the harness build (scripts/ios-sim-build.sh screenshots), and launches it once
 * per story on Tier 1 (native liquid glass) and Tier 3 (Skia fallback), the story chosen
 * by launch arguments (a deep link would stop at iOS's "Open in ActiveQueue?" prompt). A capture is
 * taken once two consecutive frames are identical. It then fails on any pixel that
 * differs (beyond reference.json's channelTolerance) from screenshots/baselines/, a story with no baseline, or a baseline with no
 * story. --update writes the captures as the new baselines instead.
 *
 * Baselines come only from the reference platform, including the Xcode that built the
 * app (an app linked against another SDK can render differently on the same simulator).
 * Elsewhere the script refuses to run unless given --off-reference: then it still checks
 * that every story renders and settles, and reports diffs without failing on them.
 * --baselines <dir> compares against (or with --update, writes) another directory, on any
 * platform: two local runs into one directory check that rendering is deterministic.
 *
 * Output (build/screenshots/): actual/, diff/ (red where pixels differ) and report.json.
 */
const { execFileSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { storyIds } = require('./storyList');

const ROOT = path.resolve(__dirname, '../..');
const REFERENCE = JSON.parse(fs.readFileSync(path.join(ROOT, 'screenshots/reference.json'), 'utf8'));
const CUSTOM_BASELINES = (() => {
  const i = process.argv.indexOf('--baselines');
  return i < 0 ? undefined : path.resolve(process.argv[i + 1]);
})();
const BASELINES = CUSTOM_BASELINES ?? path.join(ROOT, 'screenshots/baselines');
const OUT = path.join(ROOT, 'build/screenshots');
const BUNDLE_ID = 'com.b1codes.activequeue';
const DEVICE_NAME = 'aq-screenshots';
const TIERS = [1, 3];
// Stories that must look the same in light mode: the app is dark only (app.json
// userInterfaceStyle), so the system appearance must never reach a component.
const APPEARANCE_PROBES = ['core-glassheader--with-subtitle', 'queue-feedcard--default', 'queue-addsourcemodal--default'];

function arg(name) {
  const i = process.argv.indexOf(name);
  return i < 0 ? undefined : process.argv[i + 1];
}
const UPDATE = process.argv.includes('--update');
const ONLY = arg('--only');
const APP = path.resolve(arg('--app') ?? path.join(ROOT, 'build/ios/screenshots/ActiveQueue.app'));
const OFF_REFERENCE = process.argv.includes('--off-reference');
const SETTLE_TIMEOUT_MS = 30000;
const LAUNCH_TIMEOUT_MS = 45000; // a fresh simulator's first launch takes ~8 s
// A pixel has changed when any channel moved by more than this (of 255). The Tier 1 native
// material dithers by 1-2 levels from one launch to the next (measured on iOS 26.5), which
// no one can see; a layout shift, a new string or a changed color token moves far more.
const CHANNEL_TOLERANCE = REFERENCE.channelTolerance;
// System UI the app doesn't draw (reference.json says why each is there).
const MASKS = REFERENCE.masks;

const xcrun = (...args) => execFileSync('xcrun', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function runtimeAndDeviceType() {
  const { runtimes } = JSON.parse(xcrun('simctl', 'list', 'runtimes', '-j'));
  const runtime = runtimes.find((r) => r.isAvailable && r.name === REFERENCE.runtime);
  if (!runtime) {
    throw new Error(
      `The reference runtime "${REFERENCE.runtime}" isn't installed (found: ${runtimes.map((r) => r.name).join(', ')}). ` +
        'Baselines are only comparable on the reference platform.',
    );
  }
  const device = runtime.supportedDeviceTypes.find((d) => d.name === REFERENCE.device);
  if (!device) throw new Error(`${REFERENCE.runtime} has no "${REFERENCE.device}" device type`);
  return { runtime, deviceType: device };
}

/** A new simulator every run, so no setting or app state carries over. */
function freshDevice() {
  const { runtime, deviceType } = runtimeAndDeviceType();
  const { devices } = JSON.parse(xcrun('simctl', 'list', 'devices', '-j'));
  for (const d of Object.values(devices).flat()) {
    if (d.name === DEVICE_NAME) {
      try {
        xcrun('simctl', 'shutdown', d.udid);
      } catch {
        // already shut down
      }
      xcrun('simctl', 'delete', d.udid);
    }
  }
  const udid = xcrun('simctl', 'create', DEVICE_NAME, deviceType.identifier, runtime.identifier).trim();
  console.log(`capture: ${REFERENCE.device}, ${runtime.name} (${runtime.buildversion}), ${udid}`);
  return { udid, runtime };
}

function configure(udid) {
  xcrun('simctl', 'boot', udid);
  xcrun('simctl', 'bootstatus', udid, '-b');
  xcrun('simctl', 'ui', udid, 'appearance', 'dark');
  xcrun('simctl', 'ui', udid, 'content_size', 'large'); // iOS's default text size
  // Reduce Motion stills ChromaticPulse, ThermalGlow and the skeleton shimmer at their
  // first frame (each reads useReducedMotion()), so a capture can't land mid-animation.
  xcrun('simctl', 'spawn', udid, 'defaults', 'write', 'com.apple.Accessibility', 'ReduceMotionEnabled', '-bool', 'true');
  xcrun('simctl', 'spawn', udid, 'defaults', 'write', '-g', 'AppleLanguages', '-array', 'en');
  xcrun('simctl', 'spawn', udid, 'defaults', 'write', '-g', 'AppleLocale', '-string', 'en_US');
  xcrun('simctl', 'install', udid, APP);
}

let launches = 0;
const readyNonces = new Set();
let readyUrl = '';

/** Where the harness reports each launch's screen as mounted (ScreenshotRoot.tsx). */
async function startReadyServer() {
  const server = http.createServer((req, res) => {
    const nonce = new URL(req.url, 'http://localhost').searchParams.get('nonce');
    if (nonce) readyNonces.add(nonce);
    res.end('ok');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  readyUrl = `http://127.0.0.1:${server.address().port}/ready`;
  return server;
}

/**
 * A fresh process per capture, so no story inherits another's state. Returns once the
 * harness reports this launch's screen mounted: until then the screen may still be the
 * home screen or the splash, which hold still long enough to pass for a settled story.
 */
async function showStory(udid, id, tier) {
  const nonce = `${process.pid}-${++launches}`;
  xcrun('simctl', 'launch', '--terminate-running-process', udid, BUNDLE_ID,
    '-vrStory', id, '-vrTier', String(tier), '-vrNonce', nonce, '-vrReadyUrl', readyUrl);
  const started = Date.now();
  while (!readyNonces.has(nonce)) {
    if (Date.now() - started > LAUNCH_TIMEOUT_MS) throw new Error(`${id} (tier ${tier}) never reported ready`);
    await sleep(100);
  }
}

/** Pixels in a reference.json mask are left out of every comparison. */
function masked(x, y) {
  return MASKS.some((m) => x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height);
}

/** Whether two frames match outside the masks, within the channel tolerance. */
function changedPixels(a, e, width, onPixel) {
  let changed = 0;
  for (let i = 0; i < a.length; i += 4) {
    const p = i / 4;
    const delta = masked(p % width, Math.floor(p / width))
      ? 0
      : Math.max(Math.abs(a[i] - e[i]), Math.abs(a[i + 1] - e[i + 1]), Math.abs(a[i + 2] - e[i + 2]));
    const isChanged = delta > CHANNEL_TOLERANCE;
    if (isChanged) changed++;
    if (onPixel) onPixel(i, isChanged);
  }
  return changed;
}

async function png() {
  const { PNG } = await import('pngjs');
  return PNG;
}

/** Screenshots until two in a row are pixel-identical, then returns that frame. */
async function settledCapture(udid, file) {
  const PNG = await png();
  const tmp = `${file}.tmp.png`;
  const started = Date.now();
  let previous = null;
  await sleep(300);
  for (;;) {
    xcrun('simctl', 'io', udid, 'screenshot', '--type=png', tmp);
    const frame = PNG.sync.read(fs.readFileSync(tmp));
    if (previous && changedPixels(frame.data, previous.data, frame.width) === 0) {
      fs.renameSync(tmp, file);
      return frame;
    }
    if (Date.now() - started > SETTLE_TIMEOUT_MS) {
      // Keep the last two frames and what changed between them, for diagnosis.
      const base = file.replace(/\.png$/, '');
      fs.renameSync(tmp, `${base}.unsettled-last.png`);
      fs.writeFileSync(`${base}.unsettled-previous.png`, PNG.sync.write(previous));
      const diff = new PNG({ width: frame.width, height: frame.height });
      changedPixels(frame.data, previous.data, frame.width, (i, isChanged) =>
        diff.data.set(isChanged ? [255, 0, 0, 255] : [255, 255, 255, 255], i),
      );
      fs.writeFileSync(`${base}.unsettled-diff.png`, PNG.sync.write(diff));
      const err = new Error(`${path.basename(file)} never settled: something on screen keeps changing`);
      err.unsettled = true;
      throw err;
    }
    previous = frame;
    await sleep(250);
  }
}

/**
 * The harness's own screens are magenta (ScreenshotRoot.tsx), which no app color is. A
 * system alert dims it, so test the hue, not the exact value.
 */
function isHarnessError(frame) {
  const { data, width, height } = frame;
  const i = 4 * (Math.floor(height / 2) * width + 8);
  const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
  return r > 96 && b > 96 && g < 0.25 * Math.min(r, b);
}

/** Changed pixels between two frames, with a diff image: red where changed, faded elsewhere. */
async function compare(actual, baselineFile, diffFile) {
  const PNG = await png();
  if (!fs.existsSync(baselineFile)) return { status: 'missing' };
  const expected = PNG.sync.read(fs.readFileSync(baselineFile));
  if (expected.width !== actual.width || expected.height !== actual.height) {
    return { status: 'size', detail: `${actual.width}x${actual.height} vs baseline ${expected.width}x${expected.height}` };
  }
  const diff = new PNG({ width: actual.width, height: actual.height });
  const a = actual.data;
  const changed = changedPixels(a, expected.data, actual.width, (i, isChanged) => {
    if (isChanged) {
      diff.data.set([255, 0, 0, 255], i);
    } else {
      const grey = 255 - Math.round((255 - (a[i] + a[i + 1] + a[i + 2]) / 3) * 0.15);
      diff.data.set([grey, grey, grey, 255], i);
    }
  });
  if (changed === 0) return { status: 'match' };
  fs.mkdirSync(path.dirname(diffFile), { recursive: true });
  fs.writeFileSync(diffFile, PNG.sync.write(diff));
  return { status: 'diff', detail: `${changed} pixels differ` };
}

/** "26.6" -> "2660", the form Xcode stamps into a built app's Info.plist (DTXcode). */
function dtXcode(version) {
  const [major, minor = '0', patch = '0'] = version.split('.');
  return `${major}${minor}${patch}`;
}

/** Whether the app was built by the reference Xcode. Exits if not, unless --off-reference. */
function checkReference() {
  if (CUSTOM_BASELINES) return true;
  const built = execFileSync('plutil', ['-extract', 'DTXcode', 'raw', path.join(APP, 'Info.plist')], {
    encoding: 'utf8',
  }).trim();
  if (built === dtXcode(REFERENCE.xcode)) return true;
  const msg = `the app was built with Xcode ${built} (DTXcode), not the reference ${REFERENCE.xcode} (${dtXcode(REFERENCE.xcode)}).`;
  if (UPDATE) throw new Error(`refusing to write baselines: ${msg}`);
  if (!OFF_REFERENCE) {
    throw new Error(`${msg} Pass --off-reference to check the harness anyway (diffs won't fail).`);
  }
  console.warn(`capture: ${msg} Off-reference run: diffs are reported, not failed.`);
  return false;
}

async function main() {
  if (!fs.existsSync(APP)) {
    throw new Error(`No harness build at ${APP}. Run scripts/ios-sim-build.sh screenshots first.`);
  }
  const onReference = checkReference();
  const ids = storyIds().filter((id) => !ONLY || id.includes(ONLY));
  if (ids.length === 0) throw new Error(`no story matches --only ${ONLY}`);
  fs.rmSync(OUT, { recursive: true, force: true });

  const { udid, runtime } = freshDevice();
  const server = await startReadyServer();
  const results = [];
  try {
    configure(udid);
    // A just-booted simulator keeps finishing first-boot work for a while (on CI the
    // first story once never settled). One throwaway launch and a pause let it quiet down.
    await showStory(udid, ids[0], TIERS[0]);
    await sleep(10000);
    for (const tier of TIERS) {
      for (const id of ids) {
        const actualFile = path.join(OUT, 'actual', `tier${tier}`, `${id}.png`);
        fs.mkdirSync(path.dirname(actualFile), { recursive: true });
        let frame;
        try {
          await showStory(udid, id, tier);
          frame = await settledCapture(udid, actualFile);
        } catch (e) {
          if (!e.unsettled) throw e;
          // Once more from a fresh launch; a second failure is the story's own motion.
          console.warn(`  tier ${tier}  retry    ${id} (never settled; relaunching)`);
          try {
            await showStory(udid, id, tier);
            frame = await settledCapture(udid, actualFile);
          } catch (e2) {
            if (!e2.unsettled) throw e2;
            results.push({ id, tier, status: 'unsettled', detail: 'kept changing for 30 s twice; frames in actual/' });
            console.log(`  tier ${tier}  unsettled ${id}`);
            continue;
          }
        }
        if (isHarnessError(frame)) throw new Error(`the harness couldn't render ${id} (see ${actualFile})`);
        const baselineFile = path.join(BASELINES, `tier${tier}`, `${id}.png`);
        const result = UPDATE
          ? { status: 'updated' }
          : await compare(frame, baselineFile, path.join(OUT, 'diff', `tier${tier}`, `${id}.png`));
        if (UPDATE) {
          fs.mkdirSync(path.dirname(baselineFile), { recursive: true });
          fs.copyFileSync(actualFile, baselineFile);
        }
        results.push({ id, tier, ...result });
        console.log(`  tier ${tier}  ${result.status.padEnd(8)} ${id}${result.detail ? `  (${result.detail})` : ''}`);
      }
    }

    // Light mode must change nothing.
    const probes = APPEARANCE_PROBES.filter((id) => ids.includes(id));
    if (probes.length) {
      xcrun('simctl', 'ui', udid, 'appearance', 'light');
      for (const id of probes) {
        const file = path.join(OUT, 'actual', 'light', `${id}.png`);
        fs.mkdirSync(path.dirname(file), { recursive: true });
        await showStory(udid, id, 3);
        const frame = await settledCapture(udid, file);
        if (isHarnessError(frame)) throw new Error(`the harness couldn't render ${id} (see ${file})`);
        const result = await compare(frame, path.join(OUT, 'actual', 'tier3', `${id}.png`), path.join(OUT, 'diff', 'light', `${id}.png`));
        const status = result.status === 'match' ? 'match' : 'appearance';
        results.push({ id, tier: 'light', status, detail: result.detail });
        console.log(`  light   ${status.padEnd(8)} ${id}${result.detail ? `  (${result.detail})` : ''}`);
      }
    }
  } finally {
    server.close();
    try {
      xcrun('simctl', 'shutdown', udid);
      xcrun('simctl', 'delete', udid);
    } catch {
      // best effort
    }
  }

  // Baselines for stories that no longer exist.
  if (!ONLY) {
    for (const tier of TIERS) {
      const dir = path.join(BASELINES, `tier${tier}`);
      for (const f of fs.existsSync(dir) ? fs.readdirSync(dir) : []) {
        const id = f.replace(/\.png$/, '');
        if (f.endsWith('.png') && !ids.includes(id)) {
          if (UPDATE) fs.rmSync(path.join(dir, f));
          else results.push({ id, tier, status: 'stale', detail: 'baseline for a story that no longer exists' });
        }
      }
    }
  }

  const tolerated = onReference ? ['match', 'updated'] : ['match', 'updated', 'diff', 'size', 'missing', 'stale'];
  const failed = results.filter((r) => !tolerated.includes(r.status));
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(
    path.join(OUT, 'report.json'),
    JSON.stringify({ reference: REFERENCE, onReference, runtimeBuild: runtime.buildversion, results }, null, 2),
  );
  if (UPDATE) {
    console.log(`capture: wrote ${results.filter((r) => r.status === 'updated').length} baselines. Review the diff before committing.`);
  }
  if (failed.length) {
    console.error(`capture: ${failed.length} failed. Captures and diffs are in ${path.relative(process.cwd(), OUT)}/`);
    for (const r of failed) console.error(`  tier ${r.tier}  ${r.status}  ${r.id}${r.detail ? `  (${r.detail})` : ''}`);
    process.exit(1);
  }
  const differing = results.filter((r) => !['match', 'updated'].includes(r.status)).length;
  console.log(
    onReference
      ? `capture: ${results.length} screenshots, all ${UPDATE ? 'written' : 'match'}.`
      : `capture: ${results.length} screenshots rendered and settled; ${differing} differ from the reference baselines (expected off-reference).`,
  );
}

main().catch((e) => {
  console.error(`capture: ${e.message}`);
  process.exit(1);
});
