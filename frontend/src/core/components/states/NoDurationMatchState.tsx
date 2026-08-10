import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../theme';

interface NoDurationMatchStateProps {
  durationLabel?: string;
  rejectionReason?: string;
  onResetPress?: () => void;
}

export const NoDurationMatchState: React.FC<NoDurationMatchStateProps> = ({
  durationLabel,
  rejectionReason,
  onResetPress,
}) => {
  let message = 'No workout items match the requested duration window.';
  if (rejectionReason === 'duration_out_of_range') {
    message = 'Media duration must be between 5 minutes (300s) and 3 hours (10,800s) for workout sessions.';
  } else if (rejectionReason === 'no_matching_activity') {
    message = 'No activity in the catalog supports workouts of this exact duration.';
  } else if (rejectionReason === 'no_content_in_window') {
    message = 'No unconsumed feed items fit within the primary [B, B+5m] or fallback [B-2m, B] duration windows.';
  }

  return (
    <View
      style={styles.container}
      accessible={true}
      accessibilityLabel={`No duration match. ${message}`}
    >
      <View style={styles.iconBadge}>
        <Text style={styles.iconText}>⏱️</Text>
      </View>

      <Text style={styles.title}>No Duration Match Found</Text>

      {durationLabel ? (
        <View style={styles.chip}>
          <Text style={styles.chipText}>Target: {durationLabel}</Text>
        </View>
      ) : null}

      <Text style={styles.description}>{message}</Text>

      {onResetPress ? (
        <TouchableOpacity
          style={styles.button}
          onPress={onResetPress}
          activeOpacity={0.8}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel="Try a different duration"
        >
          <Text style={styles.buttonText}>Try Another Duration</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderRadius: rounded.lg,
    borderWidth: 1,
    padding: spacing.xl,
  },
  iconBadge: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderRadius: rounded.pill,
    height: 48,
    justifyContent: 'center',
    marginBottom: spacing.sm,
    width: 48,
  },
  iconText: {
    fontSize: 24,
  },
  title: {
    ...typography.title,
    color: colors.ink,
    fontSize: 18,
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  chip: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.pill,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
  },
  chipText: {
    color: colors.void,
    fontSize: 12,
    fontWeight: 'bold',
  },
  description: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 14,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    width: '100%',
  },
  buttonText: {
    ...typography.label,
    color: colors.ink,
  },
});
