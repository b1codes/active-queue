/**
 * The auditor's own tests: each rule must fire on a known-bad tree and stay quiet on the
 * fixed version, or a green sweep would prove nothing.
 */
import React from 'react';
import { ActivityIndicator, Text as RNText, TextInput, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { render, screen } from '@testing-library/react-native';
import { Text } from '@/core/components/Text';
import { colors, fontScale } from '@/core/theme';
import { auditAccessibility, type A11yRule } from '@/test-utils/a11y';
import { contrastRatio, flatten, isLargeText, parseColor } from '@/test-utils/contrast';

async function rules(ui: React.ReactElement, background?: string): Promise<A11yRule[]> {
  await render(<View style={{ backgroundColor: colors.void }}>{ui}</View>);
  return auditAccessibility(screen.root!, { background }).map((v) => v.rule);
}

const ink = { color: colors.ink };

describe('auditAccessibility', () => {
  it('passes a well-formed button', async () => {
    expect(
      await rules(
        <TouchableOpacity accessibilityRole="button" style={{ minHeight: 44, minWidth: 44 }} onPress={() => {}}>
          <Text style={ink}>Save</Text>
        </TouchableOpacity>
      )
    ).toEqual([]);
  });

  it('role: a pressable with no role', async () => {
    expect(await rules(<TouchableOpacity onPress={() => {}}><Text style={ink}>Save</Text></TouchableOpacity>)).toEqual(['role']);
  });

  it('name: an icon-only button with no label', async () => {
    const r = await rules(
      <TouchableOpacity accessibilityRole="button" onPress={() => {}}>
        <Ionicons name="close" size={20} color={colors.ink} />
      </TouchableOpacity>
    );
    expect(r).toEqual(['name']);
  });

  it('state: radio without checked, tab without selected, spinner without busy', async () => {
    expect(
      await rules(<TouchableOpacity accessibilityRole="radio" onPress={() => {}}><Text style={ink}>A</Text></TouchableOpacity>)
    ).toEqual(['state']);
    expect(
      await rules(<TouchableOpacity accessibilityRole="tab" onPress={() => {}}><Text style={ink}>A</Text></TouchableOpacity>)
    ).toEqual(['state']);
    expect(
      await rules(
        <TouchableOpacity accessibilityRole="button" accessibilityLabel="Add" onPress={() => {}}>
          <ActivityIndicator />
        </TouchableOpacity>
      )
    ).toEqual(['state']);
    expect(
      await rules(
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Add"
          accessibilityState={{ busy: true }}
          onPress={() => {}}
        >
          <ActivityIndicator />
        </TouchableOpacity>
      )
    ).toEqual([]);
  });

  it('nested: a button inside an accessible wrapper is unreachable on iOS', async () => {
    const r = await rules(
      <View accessible accessibilityLabel="Offline">
        <TouchableOpacity accessibilityRole="button" onPress={() => {}}>
          <Text style={ink}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
    expect(r).toEqual(['nested']);
  });

  it('nested: ignores content hidden from assistive tech', async () => {
    const r = await rules(
      <View accessible accessibilityLabel="Card">
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <TouchableOpacity accessibilityRole="button" onPress={() => {}}>
            <Text style={ink}>x</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
    expect(r).toEqual([]);
  });

  it('input-label: a TextInput with only a placeholder', async () => {
    const field = { color: colors.ink };
    expect(await rules(<TextInput style={field} placeholder="URL" placeholderTextColor={colors.inkMuted} />)).toEqual([
      'input-label',
    ]);
    expect(
      await rules(
        <TextInput style={field} accessibilityLabel="URL" placeholder="URL" placeholderTextColor={colors.inkMuted} />
      )
    ).toEqual([]);
  });

  it('target: under 44pt unless hitSlop makes up the difference', async () => {
    const btn = (extra: object) => (
      <TouchableOpacity accessibilityRole="button" onPress={() => {}} {...extra}>
        <Text style={ink}>x</Text>
      </TouchableOpacity>
    );
    expect(await rules(btn({ style: { height: 36 } }))).toEqual(['target']);
    expect(await rules(btn({ style: { minWidth: 30 } }))).toEqual(['target']);
    expect(await rules(btn({ style: { height: 36 }, hitSlop: 4 }))).toEqual([]);
    expect(await rules(btn({ style: { height: 36 }, hitSlop: { top: 4, bottom: 4 } }))).toEqual([]);
  });

  it('font-cap: React Native Text with no ceiling, too high a ceiling, or scaling disabled', async () => {
    expect(await rules(<RNText style={ink}>Hi</RNText>)).toEqual(['font-cap']);
    expect(await rules(<RNText style={ink} maxFontSizeMultiplier={3}>Hi</RNText>)).toEqual(['font-cap']);
    expect(await rules(<RNText style={ink} allowFontScaling={false}>Hi</RNText>)).toEqual(['font-cap']);
    expect(await rules(<Text style={ink}>Hi</Text>)).toEqual([]);
  });

  it('clip: text that outgrows its fixed-height box at the ceiling', async () => {
    const pill = (cap: number) => (
      <View style={{ height: 24, paddingHorizontal: 10 }}>
        <Text style={{ ...ink, fontSize: 13, lineHeight: 16 }} maxFontSizeMultiplier={cap}>
          12:34
        </Text>
      </View>
    );
    expect(await rules(pill(fontScale.max))).toEqual(['clip']); // 16 x 2 = 32 > 24
    expect(await rules(pill(fontScale.compact))).toEqual([]); // 16 x 1.5 = 24
    expect(
      await rules(
        <View style={{ minHeight: 24 }}>
          <Text style={{ ...ink, fontSize: 13, lineHeight: 16 }}>grows</Text>
        </View>
      )
    ).toEqual([]);
  });

  it('decorative: a lone emoji or icon VoiceOver would read', async () => {
    expect(await rules(<Text>📡</Text>)).toEqual(['decorative']);
    expect(await rules(<Ionicons name="tv-outline" size={30} color={colors.ink} />)).toEqual(['decorative']);
    expect(
      await rules(
        <Text accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          📡
        </Text>
      )
    ).toEqual([]);
    expect(await rules(<Text style={ink}>1</Text>)).toEqual([]);
  });

  it('contrast: measures text against the composited background, honoring large text', async () => {
    // Heat Core text on Strata is 4.33:1.
    expect(
      await rules(
        <View style={{ backgroundColor: colors.strata }}>
          <Text style={{ color: colors.heatCore, fontSize: 14 }}>Error</Text>
        </View>
      )
    ).toEqual(['contrast']);
    // ...but 24pt counts as large text, which needs only 3:1.
    expect(
      await rules(
        <View style={{ backgroundColor: colors.strata }}>
          <Text style={{ color: colors.heatCore, fontSize: 24 }}>Error</Text>
        </View>
      )
    ).toEqual([]);
    // Unstyled text renders black, invisible on Void.
    expect(await rules(<Text>Hello</Text>)).toEqual(['contrast']);
    // A translucent banner fill is composited onto what's beneath it.
    expect(
      await rules(
        <View style={{ backgroundColor: 'rgba(255, 255, 255, 0.9)' }}>
          <Text style={ink}>Hello</Text>
        </View>
      )
    ).toEqual(['contrast']);
  });

  it('contrast: disabled controls are exempt, as WCAG 1.4.3 allows', async () => {
    expect(
      await rules(
        <TouchableOpacity accessibilityRole="button" disabled onPress={() => {}}>
          <Text style={{ color: colors.inkFaint, fontSize: 12 }}>Start</Text>
        </TouchableOpacity>,
        colors.strata
      )
    ).toEqual([]);
  });

  it('contrast: inherits color and size through nested Text', async () => {
    expect(
      await rules(
        <Text style={{ color: colors.ink, fontSize: 14 }}>
          Total <Text style={{ fontWeight: '700' }}>12</Text>
        </Text>
      )
    ).toEqual([]);
  });
});

describe('contrast math', () => {
  it('matches the WCAG reference values', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(contrastRatio('#777777', '#ffffff')).toBeCloseTo(4.48, 2);
    expect(contrastRatio('#ffffff', '#ffffff')).toBe(1);
  });

  it('parses every color form the theme uses', () => {
    expect(parseColor('#fff')).toEqual({ r: 255, g: 255, b: 255, a: 1 });
    expect(parseColor('#FF3B3080').a).toBeCloseTo(0.5, 2);
    expect(parseColor('rgba(12, 9, 9, 0.70)')).toEqual({ r: 12, g: 9, b: 9, a: 0.7 });
    expect(parseColor('transparent').a).toBe(0);
    expect(() => parseColor('hsl(0, 0%, 0%)')).toThrow();
  });

  it('composites translucent layers bottom-up', () => {
    expect(flatten('#000000', ['rgba(255, 255, 255, 0.5)'])).toMatchObject({ r: 127.5, g: 127.5, b: 127.5 });
  });

  it('classifies large text at 24pt, or 18.66pt bold', () => {
    expect(isLargeText(24, '400')).toBe(true);
    expect(isLargeText(19, 'bold')).toBe(true);
    expect(isLargeText(19, '600')).toBe(false);
    expect(isLargeText(17, '800')).toBe(false);
  });
});
