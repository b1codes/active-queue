import type { Meta, StoryObj } from '@storybook/react-native';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { fn } from 'storybook/test';
import { ThermalGlowTouchable } from './ThermalGlowTouchable';
import { colors, rounded, spacing, typography } from '../theme';

function CardFace({ subdued = false }: { subdued?: boolean }) {
  return (
    <View style={[styles.face, subdued && styles.faceSubdued]}>
      <Text style={styles.title}>Tap or long-press this card</Text>
      <Text style={styles.subtitle}>Heat glow expands from the touch point (50ms), then dissipates (300ms).</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    margin: spacing.lg,
  },
  face: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecularLight,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.lg,
  },
  faceSubdued: {
    opacity: 0.5,
  },
  title: {
    ...typography.subtitle,
    color: colors.ink,
  },
  subtitle: {
    ...typography.bodySm,
    color: colors.inkMuted,
    marginTop: spacing.xs,
  },
});

const meta = {
  title: 'Core/ThermalGlowTouchable',
  component: ThermalGlowTouchable,
  args: {
    onPress: fn(),
    onLongPress: fn(),
    borderRadius: rounded.md,
    style: styles.wrapper,
  },
} satisfies Meta<typeof ThermalGlowTouchable>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Default Heat Corona glow, as used by FeedCard. */
export const Default: Story = {
  args: {
    children: <CardFace />,
  },
};

/** Signal-verified glow color, e.g. for a confirmation-flavored action. */
export const CustomGlowColor: Story = {
  args: {
    glowColor: colors.signalVerified,
    children: <CardFace />,
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
    children: <CardFace subdued />,
  },
};
