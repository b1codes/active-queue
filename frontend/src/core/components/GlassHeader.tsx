import React, { memo } from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { BlurView } from 'expo-blur';
import { colors, spacing, typography } from '../theme';

interface GlassHeaderProps {
  title: string;
  subtitle?: string;
  leftComponent?: React.ReactNode;
  rightComponent?: React.ReactNode;
  style?: ViewStyle;
}

/**
 * LLC Liquid Glass Header component per DESIGN.md §5 & llc-react standards
 * Real BlurView backdrop filter (intensity 20) with precomputed fallback color & specular light edge
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
      <BlurView
        intensity={20}
        tint="dark"
        experimentalBlurMethod="dimezisBlurView"
        style={styles.blurView}
      >
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
      </BlurView>
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
