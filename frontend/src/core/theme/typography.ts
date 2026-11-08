import { Platform, TextStyle } from 'react-native';

/**
 * Font Families per DESIGN.md §3
 * Geometric Sans (Montserrat) for titles/headlines + Humanist Sans (Open Sans) for body/tabular data.
 */
export const fontFamilies = {
  montserratExtraBold: Platform.select({
    ios: 'Montserrat-ExtraBold',
    android: 'Montserrat_ExtraBold',
    default: 'System',
  }),
  montserratBold: Platform.select({
    ios: 'Montserrat-Bold',
    android: 'Montserrat_Bold',
    default: 'System',
  }),
  montserratSemiBold: Platform.select({
    ios: 'Montserrat-SemiBold',
    android: 'Montserrat_SemiBold',
    default: 'System',
  }),
  openSansRegular: Platform.select({
    ios: 'OpenSans-Regular',
    android: 'OpenSans_Regular',
    default: 'System',
  }),
  openSansMedium: Platform.select({
    ios: 'OpenSans-Medium',
    android: 'OpenSans_Medium',
    default: 'System',
  }),
  openSansSemiBold: Platform.select({
    ios: 'OpenSans-SemiBold',
    android: 'OpenSans_SemiBold',
    default: 'System',
  }),
  openSansBold: Platform.select({
    ios: 'OpenSans-Bold',
    android: 'OpenSans_Bold',
    default: 'System',
  }),
} as const;

/**
 * Dynamic Type ceilings, passed as `maxFontSizeMultiplier`. Every piece of text in the app
 * scales with the iOS text size setting up to one of these, enforced by the shared `Text`
 * component and the accessibility suite.
 *
 * - `max` (2.0) is the default for all text. It takes body copy through Accessibility Size 2
 *   (body 17pt -> 34pt). Past that, single words in a 390pt-wide column start breaking
 *   mid-word, which is less readable than stopping the growth.
 * - `compact` (1.5) is for chrome that sits in a fixed-height row and would otherwise clip:
 *   the glass header, duration pills, badges, and chips. 1.5x is the largest
 *   non-accessibility size (xxxLarge, 23pt body) plus headroom.
 */
export const fontScale = {
  max: 2,
  compact: 1.5,
} as const;

/**
 * Typography Tokens per DESIGN.md §3
 * Precision-tuned for dark ground legibility (#0C0909) with optical contrast compensation.
 */
export const typography: Record<string, TextStyle> = {
  display: {
    fontFamily: fontFamilies.montserratExtraBold,
    fontSize: 34,
    fontWeight: '800',
    lineHeight: 40,
    letterSpacing: -0.5,
  },
  headline: {
    fontFamily: fontFamilies.montserratBold,
    fontSize: 26,
    fontWeight: '700',
    lineHeight: 32,
    letterSpacing: -0.35,
  },
  title: {
    fontFamily: fontFamilies.montserratBold,
    fontSize: 20,
    fontWeight: '700',
    lineHeight: 26,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontFamily: fontFamilies.montserratSemiBold,
    fontSize: 17,
    fontWeight: '600',
    lineHeight: 23,
    letterSpacing: 0,
  },
  body: {
    fontFamily: fontFamilies.openSansRegular,
    fontSize: 16,
    fontWeight: '400',
    lineHeight: 24,
    letterSpacing: 0.15,
  },
  bodySm: {
    fontFamily: fontFamilies.openSansRegular,
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 20,
    letterSpacing: 0.1,
  },
  label: {
    fontFamily: fontFamilies.openSansSemiBold,
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 17,
    letterSpacing: 0.2,
  },
  caption: {
    fontFamily: fontFamilies.openSansMedium,
    fontSize: 12,
    fontWeight: '500',
    lineHeight: 16,
    letterSpacing: 0.15,
  },
  badge: {
    fontFamily: fontFamilies.openSansBold,
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 14,
    letterSpacing: 0.3,
  },
  duration: {
    fontFamily: fontFamilies.openSansSemiBold,
    fontSize: 15,
    fontWeight: '600',
    lineHeight: 19,
    letterSpacing: 0.3,
    fontVariant: ['tabular-nums'],
  },
};

