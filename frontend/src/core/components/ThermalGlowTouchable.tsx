import React, { memo, useCallback, useEffect, useMemo, useRef } from 'react';
import { StyleProp, StyleSheet, ViewStyle } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  cancelAnimation,
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { colors } from '../theme';

const FAST_HEAT_EASE = Easing.out(Easing.quad);
const COOL_DISSIPATE_EASE = Easing.out(Easing.cubic);

const HEAT_EXCITE_MS = 50;
const COOL_DISSIPATE_MS = 300;

/**
 * Longest the glow may stay lit without `onFinalize` ever arriving.
 *
 * The glow used to be a latch: `onBegin` drove it to full opacity and *only*
 * `onFinalize` brought it back down. Any path where `onFinalize` is dropped —
 * the gesture handler being swapped mid-press, the row unmounting under
 * virtualization, RNGH cancelling when the parent ScrollView claims the touch —
 * left it lit forever, which is the stuck amber blob in ClickUp 86bbgkm4c.
 *
 * Heat that never cools is wrong on its own terms, so the dissipate is now
 * scheduled unconditionally at touch-down. Long enough that a real long-press
 * (500ms) stays lit while held; short enough that a dropped `onFinalize` reads
 * as a blip rather than an artifact.
 */
const GLOW_MAX_HOLD_MS = 1200;

const GLOW_DIAMETER = 120;
const GLOW_RADIUS = GLOW_DIAMETER / 2;

export const LIQUID_GLASS_SPRING = {
  stiffness: 180,
  damping: 12,
  mass: 1.2,
};

// Dev-only balance guard on the gesture lifecycle.
//
// The watchdog above makes a dropped `onFinalize` cosmetically harmless, which
// also makes it invisible. This keeps it observable: a touch beginning while an
// earlier one never finalized means RNGH dropped that gesture, and the glow was
// extinguished by GLOW_MAX_HOLD_MS rather than by release. Silent in the normal
// case, so it costs nothing until the underlying fault actually bites.
let glowBeginCount = 0;
let glowFinalizeCount = 0;

function noteGlowPhase(phase: 'begin' | 'finalize') {
  if (phase === 'begin') {
    const outstanding = glowBeginCount - glowFinalizeCount;
    if (outstanding > 0) {
      console.warn(
        `[ThermalGlow] ${outstanding} gesture(s) began without onFinalize — glow was ` +
          'extinguished by the GLOW_MAX_HOLD_MS watchdog, not by release (ClickUp 86bbgkm4c).'
      );
    }
    glowBeginCount += 1;
  } else {
    glowFinalizeCount += 1;
  }
}

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

  // Callbacks are held in refs so the gestures below never need rebuilding when
  // a parent hands down a fresh closure. FeedCard recreates `showOptions` on
  // every render, and rebuilding a Gesture mid-press assigns a new handler tag:
  // RNGH drops the in-flight handler, and the pending `onFinalize` goes with it.
  const onPressRef = useRef(onPress);
  const onLongPressRef = useRef(onLongPress);
  const disabledRef = useRef(disabled);
  onPressRef.current = onPress;
  onLongPressRef.current = onLongPress;
  disabledRef.current = disabled;

  const triggerOnPress = useCallback(() => {
    if (onPressRef.current && !disabledRef.current) {
      onPressRef.current();
    }
  }, []);

  const triggerOnLongPress = useCallback(() => {
    if (onLongPressRef.current && !disabledRef.current) {
      onLongPressRef.current();
    }
  }, []);

  /** Force every animated property back to its resting value. */
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
    // Covers a row unmounting mid-press, and a fresh instance inheriting a
    // recycled native view some earlier instance already lit.
    resetGlow();
    return resetGlow;
  }, [resetGlow]);

  const hasLongPress = Boolean(onLongPress);

  // Memoized so gesture identity is stable across re-renders. Only `disabled`
  // and whether a long-press handler exists can legitimately rebuild them.
  const composedGesture = useMemo(() => {
    const tapGesture = Gesture.Tap()
      .enabled(!disabled)
      .onBegin((e) => {
        'worklet';
        touchX.value = e.x;
        touchY.value = e.y;

        if (__DEV__) {
          runOnJS(noteGlowPhase)('begin');
        }

        // Phase 1 (Heat Excitation): rapid expand, then an unconditional
        // self-extinguish so the glow cannot outlive a dropped `onFinalize`.
        glowOpacity.value = withSequence(
          withTiming(1, { duration: HEAT_EXCITE_MS, easing: FAST_HEAT_EASE }),
          withDelay(
            GLOW_MAX_HOLD_MS,
            withTiming(0, { duration: COOL_DISSIPATE_MS, easing: COOL_DISSIPATE_EASE })
          )
        );
        glowScale.value = withSequence(
          withTiming(1, { duration: HEAT_EXCITE_MS, easing: FAST_HEAT_EASE }),
          withDelay(
            GLOW_MAX_HOLD_MS,
            withTiming(1.4, { duration: COOL_DISSIPATE_MS, easing: COOL_DISSIPATE_EASE })
          )
        );
        // The container scale latched the same way the glow did — a dropped
        // finalize left the card sitting 3% small as well as lit.
        cardScale.value = withSequence(
          withSpring(0.97, LIQUID_GLASS_SPRING),
          withDelay(GLOW_MAX_HOLD_MS, withSpring(1, LIQUID_GLASS_SPRING))
        );
      })
      .onFinalize((_, success) => {
        'worklet';

        if (__DEV__) {
          runOnJS(noteGlowPhase)('finalize');
        }

        // Phase 2 (Dissipate): fade & cool, pre-empting the watchdog above.
        glowOpacity.value = withTiming(0, {
          duration: COOL_DISSIPATE_MS,
          easing: COOL_DISSIPATE_EASE,
        });
        glowScale.value = withTiming(1.4, {
          duration: COOL_DISSIPATE_MS,
          easing: COOL_DISSIPATE_EASE,
        });
        cardScale.value = withSpring(1, LIQUID_GLASS_SPRING);

        if (success) {
          runOnJS(triggerOnPress)();
        }
      });

    const longPressGesture = Gesture.LongPress()
      .enabled(!disabled && hasLongPress)
      .minDuration(500)
      .onStart(() => {
        'worklet';
        runOnJS(triggerOnLongPress)();
      });

    return Gesture.Race(tapGesture, longPressGesture);
  }, [
    cardScale,
    disabled,
    glowOpacity,
    glowScale,
    hasLongPress,
    touchX,
    touchY,
    triggerOnLongPress,
    triggerOnPress,
  ]);

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
    // freshly mounted glow paints invisible on frame one.
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
