/**
 * Release build configuration: app.json and eas.json against the code that reads them
 * (ClickUp 86bcxrv0z). A mistake here builds, installs and launches fine. It surfaces
 * only on a device, as a release app talking to localhost or a tracker that never opens,
 * so it is checked here instead.
 */
import * as fs from 'fs';
import * as path from 'path';
import { TRACKER_REGISTRY } from '../../features/sessions/deepLinks';

const FRONTEND = path.resolve(__dirname, '../../..');
const REPO = path.resolve(FRONTEND, '..');

const readJson = (file: string): Record<string, unknown> =>
  JSON.parse(fs.readFileSync(path.join(FRONTEND, file), 'utf8')) as Record<string, unknown>;

interface BuildProfile {
  developmentClient?: boolean;
  distribution?: string;
  env?: Record<string, string>;
}

const expo = readJson('app.json').expo as {
  scheme: string;
  icon: string;
  splash: { image: string };
  ios: { bundleIdentifier: string; infoPlist: { LSApplicationQueriesSchemes: string[] } };
  android: { package: string; adaptiveIcon: { foregroundImage: string } };
  web: { favicon: string };
  plugins: (string | [string, unknown])[];
};
const eas = readJson('eas.json') as { build: Record<string, BuildProfile> };
const pkg = readJson('package.json') as {
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
};
const production = eas.build.production;

// Read only by dev and emulator builds. A release build must not set them.
const DEV_ONLY = new Set(['EXPO_PUBLIC_USE_EMULATOR', 'EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST']);
// Provided to production builds as an EAS environment variable (`eas env:create
// --environment production`), not committed in eas.json.
const SET_IN_EAS_ENVIRONMENT = new Set(['EXPO_PUBLIC_FIREBASE_API_KEY']);

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === '__tests__' ? [] : sourceFiles(full);
    return /\.(ts|tsx)$/.test(entry.name) && !entry.name.includes('.stories.') ? [full] : [];
  });
}

/** Every EXPO_PUBLIC_* variable the app code reads. */
const readByApp = new Set(
  ['src', 'app']
    .flatMap((dir) => sourceFiles(path.join(FRONTEND, dir)))
    .flatMap((file) =>
      [...fs.readFileSync(file, 'utf8').matchAll(/process\.env\.(EXPO_PUBLIC_[A-Z0-9_]+)/g)].map(
        (m) => m[1]
      )
    )
);

const terraformDefault = (file: string, variable: string): string => {
  const tf = fs.readFileSync(path.join(REPO, file), 'utf8');
  const block = new RegExp(`variable "${variable}" \\{[^}]*?default\\s*=\\s*"([^"]+)"`, 's');
  const match = block.exec(tf);
  if (!match) throw new Error(`no default for ${variable} in ${file}`);
  return match[1];
};

describe('eas.json build profiles', () => {
  it('finds the env vars the app reads', () => {
    expect(readByApp).toContain('EXPO_PUBLIC_API_URL');
    expect(readByApp).toContain('EXPO_PUBLIC_FIREBASE_PROJECT_ID');
  });

  it('production sets every release variable the app reads', () => {
    const missing = [...readByApp].filter(
      (v) => !DEV_ONLY.has(v) && !SET_IN_EAS_ENVIRONMENT.has(v) && !(v in (production.env ?? {}))
    );
    expect(missing).toEqual([]);
  });

  it.each(Object.entries(eas.build))('%s sets no variable the app never reads', (_name, profile) => {
    // A misspelled name (EXPO_PUBLIC_API_BASE_URL for EXPO_PUBLIC_API_URL) is silently
    // ignored, and the app falls back to its localhost default.
    const unread = Object.keys(profile.env ?? {}).filter((v) => !readByApp.has(v));
    expect(unread).toEqual([]);
  });

  it('production is a store build with no dev or emulator settings', () => {
    expect(production.developmentClient).toBeFalsy();
    expect(production.distribution ?? 'store').toBe('store');
    for (const v of DEV_ONLY) expect(production.env ?? {}).not.toHaveProperty(v);
  });

  it('production calls the API over HTTPS, never a local address', () => {
    const url = new URL(production.env?.EXPO_PUBLIC_API_URL ?? '');
    expect(url.protocol).toBe('https:');
    expect(url.hostname).not.toMatch(/^(localhost|127\.|10\.|192\.168\.)/);
    // apiClient appends /api/v1/... itself.
    expect(url.pathname).toBe('/');
  });

  it('production targets the Terraform prod project and auth domain', () => {
    expect(production.env?.EXPO_PUBLIC_FIREBASE_PROJECT_ID).toBe(
      terraformDefault('infra/environments/prod/variables.tf', 'gcp_project_id')
    );
    expect(production.env?.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN).toBe(
      terraformDefault('infra/modules/activequeue_app/variables.tf', 'custom_auth_domain')
    );
  });
});

describe('app.json', () => {
  it('declares every URL scheme the app probes with canOpenURL', () => {
    // iOS answers canOpenURL with false for any scheme missing from
    // LSApplicationQueriesSchemes, so the tracker would silently open in Safari instead
    // (SPEC §12.4 lists this as a case the manual device matrix "must" catch).
    const schemes = Object.values(TRACKER_REGISTRY)
      .map((t) => t.primarySchemeTemplate)
      .filter((t): t is string => t !== null)
      .map((t) => t.split(':')[0]);
    expect(schemes.length).toBeGreaterThan(0);
    expect(expo.ios.infoPlist.LSApplicationQueriesSchemes).toEqual(
      expect.arrayContaining(schemes)
    );
  });

  it('uses one reverse-DNS app identifier on both platforms', () => {
    expect(expo.ios.bundleIdentifier).toMatch(/^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*){2,}$/);
    expect(expo.android.package).toBe(expo.ios.bundleIdentifier);
    expect(expo.scheme).toMatch(/^[a-z][a-z0-9+.-]*$/);
  });

  it('only lists plugins that are installed', () => {
    const installed = { ...pkg.dependencies, ...pkg.devDependencies };
    const names = expo.plugins.map((p) => (Array.isArray(p) ? p[0] : p));
    expect(names.filter((n) => !(n in installed))).toEqual([]);
  });

  it('references assets that exist', () => {
    const assets = [
      expo.icon,
      expo.splash.image,
      expo.android.adaptiveIcon.foregroundImage,
      expo.web.favicon,
    ];
    expect(assets.filter((a) => !fs.existsSync(path.join(FRONTEND, a)))).toEqual([]);
  });
});
