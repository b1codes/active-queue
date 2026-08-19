import React, { memo, useCallback, useState } from 'react';
import { LayoutChangeEvent, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing, typography } from '../theme';
import { LiquidGlassSurface } from './LiquidGlassSurface';

/**
 * Height of the header's own content (title row + vertical padding) before the top safe-area
 * inset is added. Used only to seed useGlassHeaderHeight() with a close-enough value so the
 * first frame doesn't render scroll content under a not-yet-measured header; the real height
 * replaces it on the first layout pass.
 */
const GLASS_HEADER_CONTENT_HEIGHT = 60;

interface GlassHeaderProps {
  title: string;
  subtitle?: string;
  leftComponent?: React.ReactNode;
  rightComponent?: React.ReactNode;
  style?: ViewStyle;
  /**
   * Called with the header's full measured height, safe-area inset included. Screens feed this
   * into their scroll content's paddingTop — see useGlassHeaderHeight().
   */
  onHeightChange?: (height: number) => void;
}

/**
 * Tracks the overlay header's height so a screen can inset its scroll content by exactly that
 * much. Seeded from the safe-area inset plus the header's nominal content height, then
 * corrected by the first real measurement, so content never starts underneath the header.
 *
 * Pair the returned setter with GlassHeader's onHeightChange:
 *
 *   const [headerHeight, setHeaderHeight] = useGlassHeaderHeight();
 *   <FlatList contentContainerStyle={[styles.listContent, { paddingTop: headerHeight }]} />
 *   <GlassHeader title="…" onHeightChange={setHeaderHeight} />
 */
export function useGlassHeaderHeight(): [number, (height: number) => void] {
  const insets = useSafeAreaInsets();
  const [height, setHeight] = useState(insets.top + GLASS_HEADER_CONTENT_HEIGHT);
  return [height, setHeight];
}

/**
 * LLC Liquid Glass Header component per DESIGN.md §5 & llc-react standards.
 *
 * Renders through LiquidGlassSurface, which resolves the tier per react-native-glass.md §0 —
 * the native UIVisualEffectView material on iOS 26+, the Skia fallback below that.
 *
 * The header is an absolute overlay, not an in-flow band, and it is deliberately transparent
 * behind the glass: both tiers refract whatever is painted beneath them, so a screen's content
 * has to actually pass underneath for there to be anything to refract. It also absorbs the top
 * safe-area inset itself so the material extends under the status bar rather than stopping at
 * it. Screens must render it *after* their scroll view and inset that view's content by
 * useGlassHeaderHeight().
 *
 * The directional light edge is carried by this wrapper's own bottom border, since only the
 * bottom edge needs a specular highlight here.
 *
 * Counts as 1 layer against the 2-blur-layer guardrail in gpu-acceleration.md — see
 * AddSourceModal.tsx, which can share a screen with this header.
 */
export const GlassHeader: React.FC<GlassHeaderProps> = memo(({
  title,
  subtitle,
  leftComponent,
  rightComponent,
  style,
  onHeightChange,
}) => {
  const insets = useSafeAreaInsets();

  const handleLayout = useCallback(
    (e: LayoutChangeEvent) => {
      onHeightChange?.(e.nativeEvent.layout.height);
    },
    [onHeightChange]
  );

  return (
    <View style={[styles.wrapper, style]} onLayout={handleLayout}>
      <LiquidGlassSurface blurRadius={20} specularEdge="none" style={styles.blurView}>
        <View style={[styles.contentContainer, { paddingTop: insets.top + spacing.md }]}>
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
    borderBottomColor: colors.glassSpecular,
    borderBottomWidth: 1,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
    zIndex: 10,
  },
  blurView: {
    width: '100%',
  },
  contentContainer: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingBottom: spacing.md,
    paddingHorizontal: spacing.lg,
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
