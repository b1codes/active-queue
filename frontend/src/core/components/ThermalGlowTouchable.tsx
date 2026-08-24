import React, { memo, useCallback, useEffect } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  cancelAnimation,
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

const GLOW_DIAMETER = 120;
const GLOW_RADIUS = GLOW_DIAMETER / 2;

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

  /**
   * Force every animated property back to its resting value.
   *
   * Reanimated writes the glow's opacity/transform straight to the native view
   * on the UI thread, bypassing the shadow tree. Under Fabric that state can
   * outlive this component: FlatList rows are virtualized, Fabric pools and
   * reuses their native views, and it decides what to repaint by diffing the
   * new element against the props *React* last recorded. The UI-thread writes
   * were never in that record, so the diff reads "resting -> resting", emits no
   * update, and the previous row's mid-glow frame stays painted on a card that
   * was never touched.
   *
   * In-flight animations are cancelled first, otherwise the next frame would
   * simply overwrite the reset.
   */
  const resetGlow = useCallback(() => {
    cancelAnimation(glowOpacity);
    cancelAnimation(glowScale);
    cancelAnimation(cardScale);
    glowOpacity.value = 0;
    glowScale.value = 0;
    cardScale.value = 1;
    touchX.value = 0;
    touchY.value = 0;
  }, [cardScale, glowOpacity, glowScale, touchX, touchY]);

  useEffect(() => {
    // Unmount is the load-bearing half. `onBegin` drives the glow to full
    // opacity and only `onFinalize` fades it out, so a row whose finger is
    // still down when virtualization recycles it (windowSize={5} makes this
    // easy to hit) dies mid-glow and hands that state to the view pool.
    // Resetting here happens while the view is still attached, so the write is
    // a genuine change and does reach the native view before it is reused.
    // Resetting on mount covers the symmetric case of inheriting a view that
    // some earlier instance already leaked onto.
    resetGlow();
    return resetGlow;
  }, [resetGlow]);

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
    left: touchX.value - GLOW_RADIUS,
    top: touchY.value - GLOW_RADIUS,
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
            { backgroundColor: glowColor },
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
    // Resting state is declared statically as well as in `animatedGlowStyle`,
    // so React owns a baseline for every property Reanimated mutates and a
    // freshly mounted glow paints invisible on frame one rather than
    // inheriting whatever a recycled view arrived with.
    borderRadius: GLOW_RADIUS,
    height: GLOW_DIAMETER,
    left: -GLOW_RADIUS,
    opacity: 0,
    position: 'absolute',
    top: -GLOW_RADIUS,
    transform: [{ scale: 0 }],
    width: GLOW_DIAMETER,
    zIndex: 10,
  },
});
