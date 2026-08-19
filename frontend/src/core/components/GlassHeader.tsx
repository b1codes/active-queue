import React, { memo } from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { colors, spacing, typography } from '../theme';
import { LiquidGlassSurface } from './LiquidGlassSurface';

interface GlassHeaderProps {
  title: string;
  subtitle?: string;
  leftComponent?: React.ReactNode;
  rightComponent?: React.ReactNode;
  style?: ViewStyle;
}

/**
 * LLC Liquid Glass Header component per DESIGN.md §5 & llc-react standards
 * Renders through LiquidGlassSurface, which resolves the tier per react-native-glass.md §0 —
 * the native UIVisualEffectView material on iOS 26+, the Skia fallback below that. The
 * directional light edge is carried by this wrapper's own bottom border, since only the
 * bottom edge needs a specular highlight here.
 * Counts as 1 layer against the 2-blur-layer guardrail in gpu-acceleration.md — see
 * AddSourceModal.tsx, which can share a screen with this header.
 */
export const GlassHeader: React.FC<GlassHeaderProps> = memo(({
  title,
  subtitle,
  leftComponent,
  rightComponent,
  style,
}) => {
  return (
    <View style={[styles.wrapper, style]}>
      <LiquidGlassSurface blurRadius={20} specularEdge="none" style={styles.blurView}>
        <View style={styles.contentContainer}>
          <View style={styles.headerRow}>
            <View style={styles.titleContainer}>
              <View style={styles.titleRow}>
                <Text style={styles.title} numberOfLines={1} maxFontSizeMultiplier={1.5}>
                  {title}
                </Text>
                {leftComponent}
              </View>
              {subtitle ? (
                <Text style={styles.subtitle} numberOfLines={1} maxFontSizeMultiplier={1.5}>
                  {subtitle}
                </Text>
              ) : null}
            </View>

            {rightComponent ? (
              <View style={styles.rightContainer}>{rightComponent}</View>
            ) : null}
          </View>
        </View>
      </LiquidGlassSurface>
    </View>
  );
});

GlassHeader.displayName = 'GlassHeader';

const styles = StyleSheet.create({
  wrapper: {
    backgroundColor: colors.lensFlat,
    borderBottomColor: colors.glassSpecular,
    borderBottomWidth: 1,
    zIndex: 10,
  },
  blurView: {
    width: '100%',
  },
  contentContainer: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    width: '100%',
  },
  headerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  titleContainer: {
    flex: 1,
    justifyContent: 'center',
  },
  titleRow: {
    alignItems: 'center',
    flexDirection: 'row',
  },
  title: {
    ...typography.headline,
    color: colors.ink,
  },
  subtitle: {
    ...typography.bodySm,
    color: colors.inkMuted,
    marginTop: 2,
  },
  rightContainer: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
    marginLeft: spacing.md,
  },
});
