import type { Meta, StoryObj } from '@storybook/react-native';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { LiquidGlassSurface } from './LiquidGlassSurface';
import { colors, rounded, spacing, typography } from '../theme';

/**
 * Both render tiers refract whatever is painted beneath them, so every story
 * here needs real content behind the surface — a flat fill would make Tier 1
 * (native material) and Tier 3 (Skia fallback) look identical and defeat the
 * point of testing on-device.
 */
function Backdrop() {
  return (
    <View style={backdropStyles.container}>
      {['#FF3B30', '#FF9500', '#41D2B3', '#65201E'].map((c) => (
        <View key={c} style={[backdropStyles.swatch, { backgroundColor: c }]} />
      ))}
    </View>
  );
}

const backdropStyles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  swatch: {
    height: '50%',
    width: '50%',
  },
});

const styles = StyleSheet.create({
  cardWrapper: {
    margin: spacing.lg,
    height: 160,
  },
  cardContent: {
    flex: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  cardTitle: {
    ...typography.title,
    color: colors.ink,
  },
  cardBody: {
    ...typography.body,
    color: colors.inkSecondary,
    marginTop: spacing.xs,
  },
});

const meta = {
  title: 'Core/LiquidGlassSurface',
  component: LiquidGlassSurface,
  decorators: [
    (Story) => (
      <View style={{ height: 320 }}>
        <Backdrop />
        <View style={StyleSheet.absoluteFill}>
          <Story />
        </View>
      </View>
    ),
  ],
} satisfies Meta<typeof LiquidGlassSurface>;

export default meta;

type Story = StoryObj<typeof meta>;

/** A raised glass card, matching GlassHeader / FeedCard's rounded-corner usage. */
export const Default: Story = {
  args: {
    borderRadius: rounded.md,
    blurRadius: 20,
    style: styles.cardWrapper,
    children: (
      <View style={styles.cardContent}>
        <Text style={styles.cardTitle}>Liquid glass card</Text>
        <Text style={styles.cardBody}>Refracts the swatches behind it.</Text>
      </View>
    ),
  },
};

/**
 * Full-bleed modal scrim, as used by AddSourceModal — no specular edge stroke
 * since it has no border of its own to highlight.
 */
export const FullBleedScrim: Story = {
  args: {
    blurRadius: 30,
    specularEdge: 'none',
    style: { flex: 1 },
  },
};

export const NoSpecularEdge: Story = {
  args: {
    borderRadius: rounded.md,
    specularEdge: 'none',
    style: styles.cardWrapper,
  },
};
