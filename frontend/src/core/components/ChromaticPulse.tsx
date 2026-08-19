import React, { memo, useEffect } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import Animated, {
  Easing,
  interpolate,
  interpolateColor,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { colors as themeColors, rounded, spacing } from '../theme';

interface ChromaticPulseProps {
  /**
   * Palette to cycle through, in cycle order (min 2, recommended 3-4), sourced from the
   * consuming screen's own theme tokens per chromatic-pulse.md's Implementation Notes.
   * Defaults to the LLC ember cycle used by the existing skeleton states.
   */
  colors?: string[];
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

const CHROMATIC_PULSE_DURATION_MS = 3200;
const CHROMATIC_EASE = Easing.bezier(0.45, 0, 0.55, 1);
const DEFAULT_EMBER_PALETTE = [
  themeColors.heatCorona, // Corona (#FF9500)
  themeColors.heatCore,   // Core (#FF3B30)
  themeColors.emberDeep,  // Ember (#65201E)
  themeColors.heatCorona, // Loop back to Corona
];

/**
 * Signature Chromatic Pulse Loading Indicator per DESIGN.md §5 & llc-react standards
 * UI Thread Worklet execution via Reanimated v3
 * Default ember cycle: Corona (#FF9500) -> Core (#FF3B30) -> Ember (#65201E) -> Corona (#FF9500)
 * Duration: 3200ms, Easing: bezier(0.45, 0, 0.55, 1), Opacity: 0.55 -> 1.0 -> 0.55
 * Native Reduced Motion path included via useReducedMotion()
 */
export const ChromaticPulse: React.FC<ChromaticPulseProps> = memo(({ colors, style, testID }) => {
  const reduceMotion = useReducedMotion();
  const progress = useSharedValue(0);
  const palette = colors && colors.length >= 2 ? [...colors, colors[0]] : DEFAULT_EMBER_PALETTE;
  const inputRange = palette.map((_, i) => i / (palette.length - 1));

  useEffect(() => {
    if (reduceMotion) {
      progress.value = 0;
      return;
    }

    progress.value = withRepeat(
      withTiming(1, {
        duration: CHROMATIC_PULSE_DURATION_MS,
        easing: CHROMATIC_EASE,
      }),
      -1,
      false
    );
  }, [reduceMotion, progress]);

  const animatedStyle = useAnimatedStyle(() => {
    if (reduceMotion) {
      return {
        backgroundColor: palette[0],
        opacity: 1.0,
      };
    }

    const backgroundColor = interpolateColor(
      progress.value,
      inputRange,
      palette
    );

    const opacity = interpolate(
      progress.value,
      [0, 0.5, 1],
      [0.55, 1.0, 0.55]
    );

    return {
      backgroundColor,
      opacity,
    };
  });

  return (
    <Animated.View
      testID={testID}
      style={[styles.base, style, animatedStyle]}
    />
  );
});

ChromaticPulse.displayName = 'ChromaticPulse';

interface QueueSkeletonListProps {
  count?: number;
}

export const QueueSkeletonList: React.FC<QueueSkeletonListProps> = memo(({ count = 4 }) => {
  return (
    <View style={styles.skeletonContainer}>
      {Array.from({ length: count }).map((_, index) => (
        <View key={index} style={styles.skeletonRow}>
          <ChromaticPulse style={styles.skeletonThumbnail} />
          <View style={styles.skeletonContent}>
            <ChromaticPulse style={styles.skeletonTitleLine1} />
            <ChromaticPulse style={styles.skeletonTitleLine2} />
            <View style={styles.skeletonMetaRow}>
              <ChromaticPulse style={styles.skeletonProvider} />
              <ChromaticPulse style={styles.skeletonPill} />
            </View>
          </View>
        </View>
      ))}
    </View>
  );
});

QueueSkeletonList.displayName = 'QueueSkeletonList';

const styles = StyleSheet.create({
  base: {
    borderRadius: rounded.xs,
  },
  skeletonContainer: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    width: '100%',
  },
  skeletonRow: {
    backgroundColor: themeColors.lensFlat,
    borderColor: themeColors.glassEdge,
    borderTopColor: themeColors.glassSpecularLight,
    borderRadius: rounded.md,
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.sm,
  },
  skeletonThumbnail: {
    width: 104,
    height: 58.5,
    borderRadius: rounded.xs,
  },
  skeletonContent: {
    flex: 1,
    gap: spacing.xs,
  },
  skeletonTitleLine1: {
    height: 14,
    width: '85%',
    borderRadius: 4,
  },
  skeletonTitleLine2: {
    height: 14,
    width: '60%',
    borderRadius: 4,
  },
  skeletonMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  skeletonProvider: {
    height: 12,
    width: '30%',
    borderRadius: 4,
  },
  skeletonPill: {
    height: 20,
    width: 48,
    borderRadius: rounded.pill,
  },
});
