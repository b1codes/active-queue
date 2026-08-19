import React, { memo, useEffect, useState } from 'react';
import { LayoutChangeEvent, StyleSheet, View, ViewStyle } from 'react-native';
import { LiquidGlassView } from '@callstack/liquid-glass';
import {
  BackdropFilter,
  Blur,
  Canvas,
  ColorMatrix,
  LinearGradient,
  RoundedRect,
  vec,
} from '@shopify/react-native-skia';
import { colors } from '../theme';
import { useGlassTier } from '../hooks/useGlassTier';

// 160% Saturation Matrix for Liquid Glass vibrancy, per llc-react/react-native-glass.md §3
const SATURATE_160_MATRIX = [
  1.213, -0.197, -0.016, 0, 0,
  -0.087, 1.103, -0.016, 0, 0,
  -0.087, -0.197, 1.284, 0, 0,
  0, 0, 0, 1, 0,
];

// GPU Overdraw Guardrail, per gpu-acceleration.md: max 2 concurrent blur/backdrop-filter
// layers app-wide, counted per rendered instance regardless of tier. Dev-only mount counter
// so a 3rd concurrent glass layer fails loudly instead of silently degrading frame rate.
const GPU_BLUR_LAYER_BUDGET = 2;
let activeGlassLayerCount = 0;

interface LiquidGlassSurfaceProps {
  children?: React.ReactNode;
  borderRadius?: number;
  /**
   * Tier 3 only. Tier 1's blur radius is fixed by the OS material variant and cannot
   * be tuned, so this is ignored when Tier 1 resolves.
   */
  blurRadius?: number;
  style?: ViewStyle;
  /**
   * 'full' draws the 3-stop specular gradient stroke around all four edges (glass cards).
   * 'none' skips it — use when the caller renders its own directional edge (e.g. a header's
   * bottom border only) or when the surface is a full-bleed scrim with no edge at all.
   *
   * Tier 3 only. The Tier 1 native material draws its own specular edge as part of the
   * UIVisualEffectView, so this is ignored when Tier 1 resolves.
   */
  specularEdge?: 'full' | 'none';
  testID?: string;
}

/**
 * Liquid Glass surface, routed through useGlassTier() per llc-react/react-native-glass.md §0.
 *
 * Tier 1 (iOS 26+ dev build): renders through @callstack/liquid-glass's LiquidGlassView —
 * the real OS UIVisualEffectView material (§1).
 * Tier 3 (everything else): the zero-dependency Skia fallback — backdrop blur + 160%
 * saturation matrix + specular gradient stroke (§3).
 *
 * Every glass surface in the app goes through this component, so the whole app renders on
 * one tier rather than mixing native material with the hand-rolled fallback on one screen.
 */
export const LiquidGlassSurface: React.FC<LiquidGlassSurfaceProps> = memo(
  ({ children, borderRadius = 0, blurRadius = 20, style, specularEdge = 'full', testID }) => {
    const tier = useGlassTier();
    const [size, setSize] = useState({ width: 0, height: 0 });

    useEffect(() => {
      if (!__DEV__) return;
      activeGlassLayerCount += 1;
      if (activeGlassLayerCount > GPU_BLUR_LAYER_BUDGET) {
        console.warn(
          `[LiquidGlassSurface] ${activeGlassLayerCount} concurrent glass layers mounted — ` +
            `exceeds the ${GPU_BLUR_LAYER_BUDGET}-layer GPU guardrail (gpu-acceleration.md). ` +
            'Use a pre-rendered translucent color for secondary surfaces instead of another live blur.'
        );
      }
      return () => {
        activeGlassLayerCount -= 1;
      };
    }, []);

    const onLayout = (e: LayoutChangeEvent) => {
      const { width, height } = e.nativeEvent.layout;
      setSize({ width, height });
    };

    // Tier 1 — native OS material. No Canvas, no measured layout: UIKit composites the
    // blur, vibrancy and edge highlight itself, so the Skia work below is pure overhead
    // here. colorScheme is pinned to 'dark' rather than 'system' because the app is
    // dark-only (app.json userInterfaceStyle), so the glass must stay dark even when the
    // device is in light mode.
    if (tier === 1) {
      return (
        <LiquidGlassView
          testID={testID}
          effect="regular"
          colorScheme="dark"
          tintColor={colors.glassSurface}
          style={[styles.container, { borderRadius }, style]}
        >
          {children}
        </LiquidGlassView>
      );
    }

    return (
      <View testID={testID} onLayout={onLayout} style={[styles.container, { borderRadius }, style]}>
        {size.width > 0 && size.height > 0 ? (
          <Canvas style={StyleSheet.absoluteFill} pointerEvents="none">
            <BackdropFilter
              filter={
                <>
                  <Blur blur={blurRadius} />
                  <ColorMatrix matrix={SATURATE_160_MATRIX} />
                </>
              }
              clip={{ x: 0, y: 0, width: size.width, height: size.height, rx: borderRadius, ry: borderRadius }}
            >
              <RoundedRect
                x={0}
                y={0}
                width={size.width}
                height={size.height}
                r={borderRadius}
                color={colors.glassSurface}
              />
              {specularEdge === 'full' ? (
                <RoundedRect
                  x={0}
                  y={0}
                  width={size.width}
                  height={size.height}
                  r={borderRadius}
                  style="stroke"
                  strokeWidth={0.5}
                >
                  <LinearGradient
                    start={vec(0, 0)}
                    end={vec(size.width, size.height)}
                    colors={[colors.glassSpecularLight, colors.glassEdge, colors.glassSpecular]}
                  />
                </RoundedRect>
              ) : null}
            </BackdropFilter>
          </Canvas>
        ) : null}
        {children}
      </View>
    );
  }
);

LiquidGlassSurface.displayName = 'LiquidGlassSurface';

const styles = StyleSheet.create({
  container: {
    overflow: 'hidden',
    position: 'relative',
  },
});
