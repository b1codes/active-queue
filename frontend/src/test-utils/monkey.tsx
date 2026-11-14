/**
 * Seeded monkey testing: a random walk of taps, double taps, two-finger taps, long
 * presses, VoiceOver actions, scrolls, pull-to-refresh, typing, toggles, alert answers,
 * back gestures and app backgrounding over the real screens, with router.push/replace/back
 * actually changing screens. Gesture-handler touchables (feed cards) have no Pressability
 * handler, so they are reached through the accessibility actions they declare, as a
 * VoiceOver user reaches them.
 *
 * After every action the run fails on:
 * - a crash (an action or render throws),
 * - a console.error (React warnings, act() misuse, failed prop types),
 * - rendered text "undefined", "NaN" or "[object Object]",
 * - an API route the app calls that the API doesn't have,
 * and at the end, after the app settles, on an unrecoverable screen: nothing to tap and
 * nowhere to go back to.
 *
 * Jest itself fails a test on an unhandled promise rejection; the seed is in each monkey
 * test's name. (Jest gives tests a copy of `process`, so a listener here would never fire.)
 *
 * Every pick comes from the seed, so a failure reproduces with the same seed. The message
 * names the seed and the last actions taken.
 */
import React from 'react';
import { Alert, AppState, StyleSheet, type AlertButton } from 'react-native';
import { act, fireEvent, screen } from '@testing-library/react-native';
import type { TestInstance } from 'test-renderer';
import { router, setParams } from './router';
import { installFakeBackend, seededRng, type Rng } from './fakeBackend';
import { renderWithProviders } from './index';

type Node = TestInstance;
type Params = Record<string, string>;
interface Location {
  path: string;
  params: Params;
}

export interface MonkeyOptions {
  seed: number;
  steps: number;
  /** Route path (as passed to router.push) -> screen component. */
  screens: Record<string, React.ComponentType>;
  start: Location;
  /** Share of API requests that fail (network, 429, 5xx). */
  failureRate?: number;
}

const BAD_TEXT = /\bundefined\b|\bNaN\b|\[object Object\]/;
const tapEvent = { nativeEvent: {}, stopPropagation: () => {}, persist: () => {} };
const SAMPLE_TEXT = [
  'https://www.youtube.com/playlist?list=PLmonkey',
  'PLmonkey',
  'not a url',
  '',
  '   ',
  '<script>alert(1)</script>',
  '😀'.repeat(40),
  'a'.repeat(3000),
];

function nodes(root: Node | null): Node[] {
  if (!root) return [];
  const out: Node[] = [];
  const visit = (n: Node) => {
    out.push(n);
    for (const c of n.children) if (typeof c === 'object' && c !== null) visit(c);
  };
  visit(root);
  return out;
}

/** What a finger can reach: inside the top visible Modal if one is open, else everything. */
function reachable(root: Node | null): Node[] {
  const all = nodes(root);
  const modals = all.filter((n) => n.type === 'Modal' && n.props.visible !== false);
  const scope = modals.length ? nodes(modals[modals.length - 1]) : all;
  return scope.filter((n) => StyleSheet.flatten(n.props.style)?.display !== 'none');
}

function textOf(root: Node | null): string {
  return nodes(root)
    .flatMap((n) => n.children.filter((c): c is string => typeof c === 'string'))
    .join(' | ');
}

const pick = <T,>(rng: Rng, xs: T[]): T => xs[Math.floor(rng() * xs.length)];
const label = (n: Node) =>
  String(n.props.accessibilityLabel ?? n.props.testID ?? n.props.placeholder ?? n.type);

function parseTarget(to: unknown): Location {
  if (typeof to === 'string') return { path: to, params: {} };
  const { pathname, params } = to as { pathname: string; params?: Params };
  return { path: pathname, params: params ?? {} };
}

export async function runMonkey(opts: MonkeyOptions): Promise<void> {
  const rng = seededRng(opts.seed);
  const backend = installFakeBackend({ rng, failureRate: opts.failureRate ?? 0 });
  const log: string[] = [];
  const problems: string[] = [];

  const stack: Location[] = [opts.start];
  let nav: { kind: 'push' | 'replace'; to: Location } | { kind: 'back' } | null = null;
  router.push.mockImplementation((to: unknown) => (nav = { kind: 'push', to: parseTarget(to) }));
  router.replace.mockImplementation((to: unknown) => (nav = { kind: 'replace', to: parseTarget(to) }));
  router.back.mockImplementation(() => (nav = { kind: 'back' }));

  // An iOS alert is modal: while one is up, the next action must answer it.
  let alert: { title: string; buttons: AlertButton[] } | null = null;
  jest.spyOn(Alert, 'alert').mockImplementation((title, _message, buttons) => {
    alert = { title, buttons: buttons?.length ? buttons : [{ text: 'OK' }] };
  });

  const appState: ((s: string) => void)[] = [];
  jest.spyOn(AppState, 'addEventListener').mockImplementation(((_: string, cb: (s: string) => void) => {
    appState.push(cb);
    return { remove: () => appState.splice(appState.indexOf(cb), 1) };
  }) as never);

  const consoleError = jest.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    problems.push(`console.error: ${args.map(String).join(' ').slice(0, 300)}`);
  });

  // Held in an object: TypeScript can't see a closure assign a `let`, and narrows it to null.
  const current: { unmount: (() => Promise<void> | void) | null } = { unmount: null };
  const mount = async (loc: Location) => {
    if (current.unmount) await current.unmount();
    const Screen = opts.screens[loc.path];
    if (!Screen) {
      problems.push(`navigated to unknown route ${loc.path}`);
      return;
    }
    setParams(loc.params);
    const r = await renderWithProviders(<Screen />);
    current.unmount = r.unmount;
  };

  const settle = async (rounds = 3) => {
    for (let i = 0; i < rounds; i++) {
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });
    }
  };

  const applyNavigation = async () => {
    const next = nav;
    nav = null;
    if (!next) return;
    if (next.kind === 'back') {
      if (stack.length > 1) stack.pop();
    } else if (next.kind === 'push') {
      stack.push(next.to);
    } else {
      stack[stack.length - 1] = next.to;
    }
    log.push(`  -> ${stack[stack.length - 1].path} ${JSON.stringify(stack[stack.length - 1].params)}`);
    await mount(stack[stack.length - 1]);
    await settle();
  };

  const actions: { weight: number; run: () => Promise<string | null> }[] = [
    {
      weight: 6,
      run: async () => {
        const targets = reachable(screen.root).filter((n) => typeof n.props.onClick === 'function');
        if (!targets.length) return null;
        const el = pick(rng, targets);
        await act(async () => el.props.onClick(tapEvent));
        return `tap "${label(el)}"`;
      },
    },
    {
      weight: 2,
      run: async () => {
        const targets = reachable(screen.root).filter((n) => typeof n.props.onClick === 'function');
        if (!targets.length) return null;
        const el = pick(rng, targets);
        await act(async () => {
          el.props.onClick(tapEvent);
          el.props.onClick(tapEvent);
        });
        return `double-tap "${label(el)}"`;
      },
    },
    {
      weight: 1,
      run: async () => {
        const targets = reachable(screen.root).filter((n) => typeof n.props.onClick === 'function');
        if (targets.length < 2) return null;
        const a = pick(rng, targets);
        const b = pick(rng, targets.filter((t) => t !== a));
        await act(async () => {
          a.props.onClick(tapEvent);
          b.props.onClick(tapEvent);
        });
        return `two-finger tap "${label(a)}" + "${label(b)}"`;
      },
    },
    {
      weight: 1,
      run: async () => {
        const targets = reachable(screen.root).filter((n) => typeof n.props.onClick === 'function');
        if (!targets.length) return null;
        const el = pick(rng, targets);
        try {
          await fireEvent(el, 'longPress');
        } catch {
          return null; // no long-press handler
        }
        return `long-press "${label(el)}"`;
      },
    },
    {
      weight: 4,
      run: async () => {
        const targets = reachable(screen.root).filter(
          (n) => typeof n.props.onAccessibilityAction === 'function' && n.props.accessibilityActions?.length
        );
        if (!targets.length) return null;
        const el = pick(rng, targets);
        const actionName = pick(rng, el.props.accessibilityActions as { name: string }[]).name;
        await act(async () => el.props.onAccessibilityAction({ nativeEvent: { actionName } }));
        return `VoiceOver ${actionName} "${label(el)}"`;
      },
    },
    {
      weight: 2,
      run: async () => {
        const lists = reachable(screen.root).filter((n) => n.type === 'RCTScrollView');
        if (!lists.length) return null;
        const el = pick(rng, lists);
        const y = Math.floor(rng() * 4000);
        await fireEvent.scroll(el, {
          nativeEvent: {
            contentOffset: { x: 0, y },
            contentSize: { width: 390, height: 4000 },
            layoutMeasurement: { width: 390, height: 844 },
          },
        });
        if (rng() < 0.5) {
          try {
            await fireEvent(el, 'endReached');
          } catch {
            /* not a list */
          }
        }
        return `scroll to ${y}`;
      },
    },
    {
      weight: 1,
      run: async () => {
        const refreshable = reachable(screen.root).filter((n) => typeof n.props.onRefresh === 'function');
        if (!refreshable.length) return null;
        await act(async () => pick(rng, refreshable).props.onRefresh());
        return 'pull to refresh';
      },
    },
    {
      weight: 2,
      run: async () => {
        const inputs = reachable(screen.root).filter((n) => n.type === 'TextInput');
        if (!inputs.length) return null;
        const el = pick(rng, inputs);
        const text = pick(rng, SAMPLE_TEXT);
        await fireEvent.changeText(el, text);
        if (rng() < 0.5) await fireEvent(el, 'submitEditing');
        return `type ${JSON.stringify(text.slice(0, 40))} into "${label(el)}"`;
      },
    },
    {
      weight: 1,
      run: async () => {
        const toggles = reachable(screen.root).filter(
          (n) => typeof n.props.onValueChange === 'function' || typeof n.props.onChange === 'function'
        );
        const switches = toggles.filter((n) => n.type !== 'TextInput');
        if (!switches.length) return null;
        const el = pick(rng, switches);
        const value = !el.props.value;
        await act(async () => {
          el.props.onValueChange?.(value);
          el.props.onChange?.({ nativeEvent: { value } });
        });
        return `toggle "${label(el)}" to ${value}`;
      },
    },
    {
      weight: 1,
      run: async () => {
        if (stack.length < 2) return null;
        nav = { kind: 'back' };
        return 'swipe back';
      },
    },
    {
      weight: 1,
      run: async () => {
        await act(async () => [...appState].forEach((l) => l('background')));
        await settle(1);
        await act(async () => [...appState].forEach((l) => l('active')));
        return 'background and return';
      },
    },
  ];
  const totalWeight = actions.reduce((sum, a) => sum + a.weight, 0);

  const check = (when: string) => {
    const text = textOf(screen.root);
    const bad = text.match(BAD_TEXT);
    if (bad) problems.push(`rendered "${bad[0]}" ${when}: ${text.slice(0, 300)}`);
    if (backend.unknownRoutes.length) {
      problems.push(`called routes the API doesn't have: ${backend.unknownRoutes.join(', ')}`);
      backend.unknownRoutes.length = 0;
    }
  };

  const fail = (why: string) => {
    throw new Error(
      `Monkey failed (seed ${opts.seed}, start ${opts.start.path}): ${why}\n` +
        `Replay: MONKEY_SEED=${opts.seed} pnpm test -- monkey\n` +
        `Last actions:\n${log.slice(-25).join('\n')}`
    );
  };

  try {
    await mount(opts.start);
    await settle();
    check('on first render');

    for (let step = 0; step < opts.steps && !problems.length; step++) {
      let roll = rng() * totalWeight;
      const action = actions.find((a) => (roll -= a.weight) < 0) ?? actions[0];
      let did: string | null;
      try {
        if (alert) {
          const { title, buttons } = alert as { title: string; buttons: AlertButton[] };
          alert = null;
          const button = pick(rng, buttons);
          await act(async () => button.onPress?.());
          did = `answer "${title}" with "${button.text}"`;
        } else {
          did = await action.run();
        }
      } catch (err) {
        log.push(`${step}: (threw)`);
        fail(`action threw: ${err instanceof Error ? err.stack ?? err.message : String(err)}`);
        return;
      }
      if (did) log.push(`${step}: ${did}`);
      await settle();
      await applyNavigation();
      check(`after step ${step}`);
    }
    if (problems.length) fail(problems.join('\n'));

    // Let in-flight work finish, then the user must have somewhere to go.
    await settle(20);
    await applyNavigation();
    const enabled = reachable(screen.root).filter(
      (n) => typeof n.props.onClick === 'function' && n.props.accessibilityState?.disabled !== true
    );
    const scrollable = reachable(screen.root).some((n) => n.type === 'RCTScrollView');
    if (!enabled.length && !scrollable && stack.length < 2) {
      fail(`unrecoverable screen at ${stack[stack.length - 1].path}: ${textOf(screen.root).slice(0, 300)}`);
    }
    if (problems.length) fail(problems.join('\n'));
    if (process.env.MONKEY_LOG) {
      process.stdout.write(`\nseed ${opts.seed} from ${opts.start.path}:\n${log.join('\n')}\n` +
        `API calls: ${backend.calls.length}, sessions: ${[...backend.sessions.values()].map((x) => x.status).join(',')}\n`);
    }
  } finally {
    consoleError.mockRestore();
    if (current.unmount) await current.unmount();
  }
}
