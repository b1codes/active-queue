import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
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
  const durationLabel = durationSeconds
    ? `${Math.round(durationSeconds / 60)}m`
    : '';

  return (
    <TouchableOpacity
      style={styles.banner}
      onPress={() => onResumePress(sessionId)}
      activeOpacity={0.85}
      accessible={true}
      accessibilityRole="button"
      accessibilityLabel={`Active workout session in progress for ${activityId} ${durationLabel}. Tap to resume session.`}
    >
      <View style={styles.leftRow}>
        <View style={styles.pulsingDot} />
        <View style={styles.textContainer}>
          <Text style={styles.title}>Workout Session In Progress</Text>
          <Text style={styles.subtitle}>
            {activityId.toUpperCase()} {durationLabel ? `• ${durationLabel}` : ''}
          </Text>
        </View>
      </View>

      <View style={styles.resumeBadge}>
        <Text style={styles.resumeText}>Resume →</Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  banner: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.signalVerified,
    borderRadius: rounded.md,
    borderWidth: 1.5,
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginHorizontal: spacing.lg,
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
    backgroundColor: colors.signalVerified,
    borderRadius: rounded.xs,
    marginLeft: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  resumeText: {
    color: colors.void,
    fontSize: 12,
    fontWeight: 'bold',
  },
});
