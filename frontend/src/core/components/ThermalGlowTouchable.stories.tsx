import type { Meta, StoryObj } from '@storybook/react-native';
import React from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
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

/**
 * Deliberately aggressive virtualization so Fabric recycles native views after
 * only a short scroll — the condition that surfaced the glow-leak bug.
 */
function RecyclingList(args: React.ComponentProps<typeof ThermalGlowTouchable>) {
  const rows = React.useMemo(
    () => Array.from({ length: 60 }, (_, i) => ({ id: `row-${i}`, label: `Row ${i + 1}` })),
    []
  );

  return (
    <FlatList
      data={rows}
      keyExtractor={(row) => row.id}
      initialNumToRender={4}
      maxToRenderPerBatch={4}
      windowSize={3}
      renderItem={({ item }) => (
        <ThermalGlowTouchable {...args} style={styles.wrapper}>
          <View style={styles.face}>
            <Text style={styles.title}>{item.label}</Text>
            <Text style={styles.subtitle}>
              Hold this row, then drag to scroll without lifting your finger.
            </Text>
          </View>
        </ThermalGlowTouchable>
      )}
    />
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

/**
 * Regression harness for the glow "leaking" onto an unrelated recycled row.
 *
 * To verify: press and hold any row, then — without lifting — drag to scroll
 * until that row is virtualized away, and release somewhere further down the
 * list. Keep scrolling and watch the rows that come back into view.
 *
 * Correct behavior: no row ever shows an amber glow you did not touch.
 * The bug looked like a stuck 120x120 amber circle riding along with content
 * on a row that was never pressed, because the held row unmounted mid-glow and
 * handed that UI-thread state to Fabric's view pool.
 */
export const VirtualizedRecycling: Story = {
  args: {
    children: <CardFace />,
  },
  render: (args) => <RecyclingList {...args} />,
};
