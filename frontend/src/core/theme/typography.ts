import { TextStyle } from 'react-native';

/**
 * Typography Tokens per DESIGN.md §3
 * Montserrat (geometric headlines) + Open Sans (humanist body & tabular data)
 */
export const typography: Record<string, TextStyle> = {
  display: {
    fontFamily: 'System', // Montserrat-ExtraBold fallback
    fontSize: 34,
    fontWeight: '800',
    lineHeight: 38,
    letterSpacing: -0.5,
  },
  headline: {
    fontFamily: 'System', // Montserrat-Bold fallback
    fontSize: 26,
    fontWeight: '700',
    lineHeight: 30,
    letterSpacing: -0.35,
  },
  title: {
    fontFamily: 'System', // Montserrat-Bold fallback
    fontSize: 20,
    fontWeight: '700',
    lineHeight: 25,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontFamily: 'System', // Montserrat-SemiBold fallback
    fontSize: 17,
    fontWeight: '600',
    lineHeight: 22,
    letterSpacing: 0,
  },
  body: {
    fontFamily: 'System', // OpenSans-Regular fallback
    fontSize: 16,
    fontWeight: '400',
    lineHeight: 24,
    letterSpacing: 0,
  },
  bodySm: {
    fontFamily: 'System', // OpenSans-Regular fallback
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 20,
    letterSpacing: 0,
  },
  label: {
    fontFamily: 'System', // OpenSans-SemiBold fallback
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 16,
    letterSpacing: 0.2,
  },
  caption: {
    fontFamily: 'System', // OpenSans-Medium fallback
    fontSize: 12,
    fontWeight: '500',
    lineHeight: 15,
    letterSpacing: 0.1,
  },
  badge: {
    fontFamily: 'System', // OpenSans-Bold fallback
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 14,
    letterSpacing: 0.3,
  },
  duration: {
    fontFamily: 'System', // OpenSans-SemiBold fallback with tabular nums
    fontSize: 15,
    fontWeight: '600',
    lineHeight: 18,
    letterSpacing: 0.3,
    fontVariant: ['tabular-nums'],
  },
};
