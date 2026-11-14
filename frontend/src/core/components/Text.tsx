import React from 'react';
import { Text as RNText, type TextProps } from 'react-native';
import { fontScale } from '../theme';

/**
 * The app's Text. It has the same API as React Native's, but it defaults
 * `maxFontSizeMultiplier` to `fontScale.max`, so every string scales with the iOS text
 * size setting up to a ceiling the layouts were checked against. A caller can lower the
 * ceiling (fontScale.compact for fixed-height chrome) but should never raise or remove it.
 *
 * ESLint bans importing Text from react-native outside this file.
 */
export function Text({
  maxFontSizeMultiplier = fontScale.max,
  ...props
}: TextProps & { ref?: React.Ref<RNText> }) {
  return <RNText maxFontSizeMultiplier={maxFontSizeMultiplier} {...props} />;
}
