import type { Meta, StoryObj } from '@storybook/react-native';
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fn } from 'storybook/test';
import { GlassHeader } from './GlassHeader';
import { colors, rounded, spacing, typography } from '../theme';

/**
 * GlassHeader is an absolute overlay, not an in-flow band — it renders over
 * whatever scroll content is behind it, and is deliberately transparent so
 * that content refracts through the glass. This decorator stands in for a
 * screen's scroll content so the blur/vibrancy has something to refract.
 */
function BackdropContent() {
  return (
    <View style={backdropStyles.container}>
      {Array.from({ length: 6 }).map((_, i) => (
        <View key={i} style={backdropStyles.row} />
      ))}
    </View>
  );
}

const backdropStyles = StyleSheet.create({
  container: {
    flex: 1,
    gap: spacing.sm,
    padding: spacing.lg,
    paddingTop: 140,
  },
  row: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    height: 64,
  },
});

const styles = StyleSheet.create({
  countBadge: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.pill,
    marginLeft: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  countBadgeText: {
    ...typography.label,
    color: colors.void,
    fontSize: 12,
    fontWeight: 'bold',
  },
  addButton: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.md,
  },
  addButtonText: {
    ...typography.label,
    color: colors.ink,
  },
  iconButton: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 44,
  },
});

const meta = {
  title: 'Core/GlassHeader',
  component: GlassHeader,
  decorators: [
    (Story) => (
      <View style={{ flex: 1, minHeight: 320 }}>
        <BackdropContent />
        <Story />
      </View>
    ),
  ],
  args: {
    onHeightChange: fn(),
  },
} satisfies Meta<typeof GlassHeader>;

export default meta;

type Story = StoryObj<typeof meta>;

/** As used on the Settings screen — title only, no left/right accessories. */
export const Default: Story = {
  args: {
    title: 'Settings',
  },
};

/**
 * As used on the queue screen: an unconsumed-count badge on the left, and
 * "Add Source" + sign-out icon actions on the right.
 */
export const WithBadgeAndActions: Story = {
  args: {
    title: 'Active Queue',
    leftComponent: (
      <View style={styles.countBadge}>
        <Text style={styles.countBadgeText}>128</Text>
      </View>
    ),
    rightComponent: (
      <>
        <TouchableOpacity
          style={styles.addButton}
          accessible
          accessibilityRole="button"
          accessibilityLabel="Add Source"
        >
          <Text style={styles.addButtonText}>+ Add Source</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.iconButton}
          accessible
          accessibilityRole="button"
          accessibilityLabel="Sign Out"
        >
          <Ionicons name="log-out-outline" size={20} color={colors.inkSecondary} />
        </TouchableOpacity>
      </>
    ),
  },
};

export const WithSubtitle: Story = {
  args: {
    title: 'Workout Session',
    subtitle: 'Elapsed 12:04',
  },
};
