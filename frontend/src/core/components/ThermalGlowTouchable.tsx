import React, { memo } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { colors } from '../theme';

const FAST_HEAT_EASE = Easing.out(Easing.quad);
const COOL_DISSIPATE_EASE = Easing.out(Easing.cubic);

export const LIQUID_GLASS_SPRING = {
  stiffness: 180,
  damping: 12,
  mass: 1.2,
};

interface ThermalGlowTouchableProps {
  children: React.ReactNode;
  onPress?: () => void;
  onLongPress?: () => void;
  borderRadius?: number;
  glowColor?: string;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
  accessible?: boolean;
  accessibilityRole?: 'button' | 'link' | 'tab' | 'checkbox' | 'radio';
  accessibilityLabel?: string;
  accessibilityHint?: string;
  accessibilityState?: { selected?: boolean; disabled?: boolean };
}

/**
 * React Native Thermal Glow Touchable per DESIGN.md §5 & llc-react standards
 * Touch = Heat. Upon tap/press, a radial heat glow expands rapidly (50ms) at the contact point
 * and dissipates smoothly (300ms) back into the glass panel on release.
 * Container scale spring physics: stiffness: 180, damping: 12, mass: 1.2
 */
export const ThermalGlowTouchable: React.FC<ThermalGlowTouchableProps> = memo(({
  children,
  onPress,
  onLongPress,
  borderRadius = 14,
  glowColor = colors.thermalGlowDefault, // Thermal Heat Corona default per DESIGN.md §2
  disabled = false,
  style,
  testID,
  accessible,
  accessibilityRole,
  accessibilityLabel,
  accessibilityHint,
  accessibilityState,
}) => {
  const touchX = useSharedValue(0);
  const touchY = useSharedValue(0);
  const glowScale = useSharedValue(0);
  const glowOpacity = useSharedValue(0);
  const cardScale = useSharedValue(1);

  const triggerOnPress = () => {
    if (onPress && !disabled) {
      onPress();
    }
  };

  const triggerOnLongPress = () => {
    if (onLongPress && !disabled) {
      onLongPress();
    }
  };

  const tapGesture = Gesture.Tap()
    .enabled(!disabled)
    .onBegin((e) => {
      'worklet';
      touchX.value = e.x;
      touchY.value = e.y;

      // Phase 1 (Heat Excitation): Rapid expand (50ms)
      glowScale.value = withTiming(1, { duration: 50, easing: FAST_HEAT_EASE });
      glowOpacity.value = withTiming(1, { duration: 50, easing: FAST_HEAT_EASE });
      cardScale.value = withSpring(0.97, LIQUID_GLASS_SPRING);
    })
    .onFinalize((_, success) => {
      'worklet';
      // Phase 2 (Dissipate): Fade & cool (300ms)
      glowOpacity.value = withTiming(0, { duration: 300, easing: COOL_DISSIPATE_EASE });
      glowScale.value = withTiming(1.4, { duration: 300, easing: COOL_DISSIPATE_EASE });
      cardScale.value = withSpring(1, LIQUID_GLASS_SPRING);

      if (success) {
        runOnJS(triggerOnPress)();
      }
    });

  const longPressGesture = Gesture.LongPress()
    .enabled(!disabled && Boolean(onLongPress))
    .minDuration(500)
    .onStart(() => {
      'worklet';
      runOnJS(triggerOnLongPress)();
    });

  const composedGesture = Gesture.Race(tapGesture, longPressGesture);

  const animatedGlowStyle = useAnimatedStyle(() => ({
    left: touchX.value - 60,
    top: touchY.value - 60,
    transform: [{ scale: glowScale.value }],
    opacity: glowOpacity.value,
  }));

  const animatedContainerStyle = useAnimatedStyle(() => ({
    transform: [{ scale: cardScale.value }],
  }));

  return (
    <GestureDetector gesture={composedGesture}>
      <Animated.View
        testID={testID}
        accessible={accessible}
        accessibilityRole={accessibilityRole || 'button'}
        accessibilityLabel={accessibilityLabel}
        accessibilityHint={accessibilityHint}
        accessibilityState={accessibilityState}
        style={[
          styles.container,
          { borderRadius },
          style,
          animatedContainerStyle,
        ]}
      >
        {children}

        {/* Thermal Glow Overlay Circle */}
        <Animated.View
          pointerEvents="none"
          style={[
            styles.glowCircle,
            { backgroundColor: glowColor, borderRadius: 60 },
            animatedGlowStyle,
          ]}
        />
      </Animated.View>
    </GestureDetector>
  );
});

ThermalGlowTouchable.displayName = 'ThermalGlowTouchable';

const styles = StyleSheet.create({
  container: {
    overflow: 'hidden',
    position: 'relative',
  },
  glowCircle: {
    height: 120,
    position: 'absolute',
    width: 120,
    zIndex: 10,
  },
});
