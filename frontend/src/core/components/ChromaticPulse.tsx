import React, { memo, useEffect, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle,
} from 'react-native';
import { colors, rounded, spacing } from '../theme';

interface ChromaticPulseProps {
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * Signature Chromatic Pulse Loading Indicator per DESIGN.md §5
 * Ember cycle: Corona (#FF9500) -> Core (#FF3B30) -> Ember (#65201E) -> Corona (#FF9500)
 * Duration: 3200ms, Easing: bezier(0.45, 0, 0.55, 1), Opacity: 0.55 -> 1.0 -> 0.55
 * Mandated Reduced Motion path included.
 */
export const ChromaticPulse: React.FC<ChromaticPulseProps> = memo(({ style, testID }) => {
  const [reduceMotion, setReduceMotion] = useState(false);
  const animValue = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let isMounted = true;

    // Check reduced motion state
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (isMounted) {
        setReduceMotion(enabled);
      }
    });

    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      (enabled) => {
        if (isMounted) {
          setReduceMotion(enabled);
        }
      }
    );

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (reduceMotion) {
      animValue.stopAnimation();
      return;
    }

    const animation = Animated.loop(
      Animated.timing(animValue, {
        toValue: 1,
        duration: 3200,
        easing: Easing.bezier(0.45, 0, 0.55, 1),
        useNativeDriver: false,
      })
    );

    animation.start();

    return () => {
      animation.stop();
    };
  }, [animValue, reduceMotion]);

  if (reduceMotion) {
    return (
      <Animated.View
        testID={testID}
        style={[
          styles.base,
          {
            backgroundColor: colors.heatCorona,
            opacity: 1.0,
          },
          style,
        ]}
      />
    );
  }

  // Ember Cycle Interpolation per DESIGN.md §5:
  // Corona (#FF9500) -> Core (#FF3B30) -> Ember (#65201E) -> Corona (#FF9500)
  const backgroundColor = animValue.interpolate({
    inputRange: [0, 0.33, 0.66, 1],
    outputRange: [
      colors.heatCorona,
      colors.heatCore,
      colors.emberDeep,
      colors.heatCorona,
    ],
  });

  const opacity = animValue.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0.55, 1.0, 0.55],
  });

  return (
    <Animated.View
      testID={testID}
      style={[
        styles.base,
        {
          backgroundColor,
          opacity,
        },
        style,
      ]}
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
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
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
