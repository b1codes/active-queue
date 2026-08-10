import React, { useEffect, useState } from 'react';
import { AccessibilityInfo, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, rounded, spacing, typography } from '../../theme';

interface ActiveSessionBannerProps {
  sessionId: string;
  activityId?: string;
  durationSeconds?: number;
  onResumePress: (sessionId: string) => void;
}

export const ActiveSessionBanner: React.FC<ActiveSessionBannerProps> = ({
  sessionId,
  activityId = 'Workout',
  durationSeconds,
  onResumePress,
}) => {
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let isMounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (isMounted) setReduceMotion(enabled);
    });

    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', (enabled) => {
      if (isMounted) setReduceMotion(enabled);
    });

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, []);

  const safeDuration = durationSeconds && durationSeconds > 0 ? Math.round(durationSeconds / 60) : 0;
  const durationLabel = safeDuration > 0 ? `${safeDuration}m` : '';
  const safeActivityLabel = (activityId || 'Workout').toUpperCase().trim();

  return (
    <View style={styles.outerWrapper}>
      <TouchableOpacity
        style={styles.banner}
        onPress={() => onResumePress(sessionId)}
        activeOpacity={0.85}
        accessible={true}
        accessibilityRole="button"
        accessibilityLabel={`Active workout session in progress for ${safeActivityLabel} ${durationLabel}. Tap to resume session.`}
      >
        <View style={styles.leftRow}>
          <View style={[styles.pulsingDot, reduceMotion && styles.staticDot]} />
          <View style={styles.textContainer}>
            <Text style={styles.title} numberOfLines={1}>Workout Session In Progress</Text>
            <Text style={styles.subtitle} numberOfLines={1}>
              {safeActivityLabel} {durationLabel ? `• ${durationLabel}` : ''}
            </Text>
          </View>
        </View>

        <View style={styles.resumeBadge}>
          <Text style={styles.resumeText}>Resume</Text>
          <Ionicons name="arrow-forward" size={12} color={colors.void} style={styles.arrowIcon} />
        </View>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  outerWrapper: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    width: '100%',
  },
  banner: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.signalVerified,
    borderRadius: rounded.md,
    borderWidth: 1.5,
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginVertical: spacing.sm,
    padding: spacing.md,
  },
  leftRow: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
  },
  pulsingDot: {
    backgroundColor: colors.signalVerified,
    borderRadius: rounded.pill,
    height: 10,
    marginRight: spacing.sm,
    width: 10,
  },
  staticDot: {
    opacity: 0.9,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    ...typography.label,
    color: colors.signalVerified,
    fontSize: 14,
    fontWeight: 'bold',
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 12,
  },
  resumeBadge: {
    alignItems: 'center',
    backgroundColor: colors.signalVerified,
    borderRadius: rounded.xs,
    flexDirection: 'row',
    marginLeft: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  resumeText: {
    color: colors.void,
    fontSize: 12,
    fontWeight: 'bold',
  },
  arrowIcon: {
    marginLeft: 3,
  },
});
