import React, { memo, useState } from 'react';
import { LayoutChangeEvent, StyleSheet, View, ViewStyle } from 'react-native';
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

interface LiquidGlassSurfaceProps {
  children?: React.ReactNode;
  borderRadius?: number;
  blurRadius?: number;
  style?: ViewStyle;
  /**
   * 'full' draws the 3-stop specular gradient stroke around all four edges (glass cards).
   * 'none' skips it — use when the caller renders its own directional edge (e.g. a header's
   * bottom border only) or when the surface is a full-bleed scrim with no edge at all.
   */
  specularEdge?: 'full' | 'none';
  testID?: string;
}

/**
 * Tier 3 (zero-dependency) Liquid Glass surface per llc-react/react-native-glass.md §3 —
 * Skia backdrop blur + 160% saturation matrix + specular gradient stroke.
 *
 * Routed through useGlassTier() so this becomes a no-op passthrough once Tier 1/2 packages
 * are installed and a higher tier resolves; today useGlassTier() always returns 3.
 */
export const LiquidGlassSurface: React.FC<LiquidGlassSurfaceProps> = memo(
  ({ children, borderRadius = 0, blurRadius = 20, style, specularEdge = 'full', testID }) => {
    const tier = useGlassTier();
    const [size, setSize] = useState({ width: 0, height: 0 });

    const onLayout = (e: LayoutChangeEvent) => {
      const { width, height } = e.nativeEvent.layout;
      setSize({ width, height });
    };

    return (
      <View testID={testID} onLayout={onLayout} style={[styles.container, { borderRadius }, style]}>
        {tier === 3 && size.width > 0 && size.height > 0 ? (
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
