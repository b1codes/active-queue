/**
 * iOS accessibility settings the app must follow: Reduce Transparency, Reduce Motion, and
 * legibility of text on glass whatever scrolls beneath it.
 */
import fs from 'fs';
import path from 'path';
import React from 'react';
import { AccessibilityInfo } from 'react-native';
import { act, render, screen } from '@testing-library/react-native';
import * as LiquidGlass from '@callstack/liquid-glass';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GlassHeader, LiquidGlassSurface } from '@/core/components';
import { Text } from '@/core/components/Text';
import { __resetGlassTierCacheForTests } from '@/core/hooks/useGlassTier';
import { colors } from '@/core/theme';
import { auditAccessibility, expectAccessible, formatViolations } from '@/test-utils/a11y';
import { contrastRatio, flatten } from '@/test-utils/contrast';

type Listener = (enabled: boolean) => void;
const listeners = new Map<string, Listener[]>();

function mockSetting(event: string, getter: 'isReduceTransparencyEnabled' | 'isReduceMotionEnabled', initial: boolean) {
  jest.spyOn(AccessibilityInfo, getter).mockResolvedValue(initial);
  jest.spyOn(AccessibilityInfo, 'addEventListener').mockImplementation(((name: string, cb: Listener) => {
    listeners.set(name, [...(listeners.get(name) ?? []), cb]);
    return { remove: () => listeners.set(name, (listeners.get(name) ?? []).filter((l) => l !== cb)) };
  }) as never);
  return (enabled: boolean) => act(() => (listeners.get(event) ?? []).forEach((l) => l(enabled)));
}

function setTier(tier: 1 | 3) {
  Object.defineProperty(LiquidGlass, 'isLiquidGlassSupported', { value: tier === 1, configurable: true });
  __resetGlassTierCacheForTests();
}

const SRC = path.resolve(__dirname, '../..');
const APP = path.resolve(SRC, '../app');

function sources(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === '__tests__' ? [] : sources(full);
    return /\.tsx?$/.test(e.name) ? [full] : [];
  });
}

afterEach(() => {
  listeners.clear();
  setTier(3);
});

describe('Reduce Transparency', () => {
  it.each([1, 3] as const)('turns Tier %s glass into an opaque surface, live', async (tier) => {
    setTier(tier);
    const toggle = mockSetting('reduceTransparencyChanged', 'isReduceTransparencyEnabled', true);
    await render(
      <LiquidGlassSurface testID="glass">
        <Text>content</Text>
      </LiquidGlassSurface>
    );
    await act(async () => {});
    const solid = screen.getByTestId('glass');
    expect(solid.type).toBe('View');
    expect(solid).toHaveStyle({ backgroundColor: colors.glassSolid });
    expect(screen.getByText('content')).toBeTruthy();

    await toggle(false);
    // Back to glass: Tier 1 is the native view, Tier 3 a View with no fill of its own.
    expect(screen.getByTestId('glass')).not.toHaveStyle({ backgroundColor: colors.glassSolid });
  });

  it('is off until the setting says otherwise', async () => {
    mockSetting('reduceTransparencyChanged', 'isReduceTransparencyEnabled', false);
    await render(<LiquidGlassSurface testID="glass" />);
    await act(async () => {});
    expect(screen.getByTestId('glass')).not.toHaveStyle({ backgroundColor: colors.glassSolid });
  });
});

describe('text on glass', () => {
  // Bright things that can scroll under the overlay header: white thumbnails, a selected
  // chip (Ink), a Heat Core button, a Signal Verified badge.
  const beneath = ['#FFFFFF', colors.ink, colors.heatCore, colors.signalVerified];

  async function renderHeader() {
    await render(
      <SafeAreaProvider initialMetrics={{ frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } }}>
        <GlassHeader title="Your Queue" subtitle="1,284 unconsumed" />
      </SafeAreaProvider>
    );
    await act(async () => {});
  }

  it.each(beneath)('the Tier 3 header stays AA over %s', async (under) => {
    setTier(3);
    await renderHeader();
    // Tier 3 draws its 5% glass fill above the scrim, so add it to what's beneath.
    const bg = flatten(under, [colors.glassScrim, colors.glassSurface]);
    for (const color of [colors.ink, colors.inkMuted]) {
      expect(contrastRatio(color, bg)).toBeGreaterThanOrEqual(4.5);
    }
    const violations = auditAccessibility(screen.root!, { background: under });
    expect(formatViolations(violations)).toBe('');
  });

  it('would fail without the scrim', () => {
    // The regression this guards: the bare 5% tint over a Heat Core button.
    const bare = flatten(colors.heatCore, [colors.glassSurface]);
    expect(contrastRatio(colors.inkMuted, bare)).toBeLessThan(2);
  });

  it('marks the header title as a heading for the VoiceOver rotor', async () => {
    await renderHeader();
    expect(screen.getByRole('header', { name: 'Your Queue' })).toBeTruthy();
    expectAccessible();
  });

  it('keeps the modal sheet and banners AA on their translucent fills', () => {
    // AddSourceModal: raised lens over the 70% Void overlay over the dimmed screen.
    const sheet = flatten(colors.void, [colors.modalOverlayBg, colors.lensFlatRaised]);
    expect(contrastRatio(colors.inkSecondary, sheet)).toBeGreaterThanOrEqual(4.5);
    // Corona-tinted alert banners over Void.
    const banner = flatten(colors.void, [colors.bannerAlertBg]);
    for (const c of [colors.ink, colors.inkSecondary, colors.inkMuted, colors.heatCorona]) {
      expect(contrastRatio(c, banner)).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe('theme tokens', () => {
  const grounds = {
    void: colors.void,
    substrate: colors.substrate,
    strata: colors.strata,
    lensFlat: colors.lensFlat,
    lensFlatRaised: colors.lensFlatRaised,
    glassOverVoid: flatten(colors.void, [colors.glassSurface]),
  };
  const textTokens = ['ink', 'inkSecondary', 'inkMuted', 'heatCoreInk', 'signalVerified', 'heatCorona'] as const;

  it.each(textTokens)('%s is AA body text on every ground', (token) => {
    for (const [name, bg] of Object.entries(grounds)) {
      const ratio = contrastRatio(colors[token], typeof bg === 'string' ? bg : bg);
      if (ratio < 4.5) throw new Error(`${token} on ${name} is ${ratio.toFixed(2)}:1`);
    }
  });

  it('inkFaint clears 3:1 for icons and large text on every ground', () => {
    for (const bg of Object.values(grounds)) {
      expect(contrastRatio(colors.inkFaint, bg)).toBeGreaterThanOrEqual(3);
    }
  });

  it('Void labels on Heat Core fills (the Black Label Rule) are AA', () => {
    expect(contrastRatio(colors.void, colors.heatCore)).toBeGreaterThanOrEqual(4.5);
  });
});

describe('Reduce Motion', () => {
  // Reanimated's withTiming/withSpring/withSequence/withDelay default to ReduceMotion.System:
  // with the setting on they jump to their final value, which is how ThermalGlow's glow and
  // press-scale stay off without code of their own. That only holds while nothing opts out
  // and no animation runs outside Reanimated, so the source is checked for both.
  const files = [...sources(SRC), ...sources(APP)].filter((f) => !f.includes('test-utils'));

  it('finds the sources', () => {
    expect(files.length).toBeGreaterThan(40);
  });

  it('no Reanimated animation opts out of the system setting', () => {
    const offenders = files.filter((f) => /ReduceMotion\.Never/.test(fs.readFileSync(f, 'utf8')));
    expect(offenders).toEqual([]);
  });

  it('nothing animates through React Native core Animated or LayoutAnimation, which ignore it', () => {
    const offenders = files.filter((f) => {
      const src = fs.readFileSync(f, 'utf8');
      return (
        /\bLayoutAnimation\b/.test(src) ||
        /import\s*\{[^}]*\bAnimated\b[^}]*\}\s*from\s*'react-native'/.test(src)
      );
    });
    expect(offenders).toEqual([]);
  });

  it('modals only cross-fade, the transition Apple recommends under Reduce Motion', () => {
    const slides = files.filter((f) => /animationType=["']slide["']/.test(fs.readFileSync(f, 'utf8')));
    expect(slides).toEqual([]);
  });

});
