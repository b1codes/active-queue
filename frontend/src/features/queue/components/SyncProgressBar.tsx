import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../../core/theme';
import { useQueueStore } from '../queueStore';

export const SyncProgressBar: React.FC = () => {
  const { syncProgress, cancelSync } = useQueueStore();
  const { isSyncing, itemsSyncedTotal, estimatedTotal, error } = syncProgress;

  if (!isSyncing && !error) {
    return null;
  }

  const est = estimatedTotal || 1000;
  const progressRatio = Math.min(itemsSyncedTotal / est, 1.0);
  const progressPercent = Math.round(progressRatio * 100);

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.titleText}>
          {isSyncing ? 'Syncing Content Source...' : 'Sync Status'}
        </Text>
        {isSyncing && (
          <TouchableOpacity onPress={cancelSync} style={styles.cancelButton}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
        )}
      </View>

      {error ? (
        <Text style={styles.errorText}>{error}</Text>
      ) : (
        <>
          <Text style={styles.progressText}>
            {itemsSyncedTotal} of ~{estimatedTotal ? estimatedTotal : '1,000+'} items synced
          </Text>

          <View style={styles.trackBackground}>
            <View style={[styles.trackFill, { width: `${progressPercent}%` }]} />
          </View>
        </>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    marginHorizontal: spacing.lg,
    marginVertical: spacing.sm,
    padding: spacing.md,
  },
  headerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  titleText: {
    ...typography.subtitle,
    color: colors.ink,
  },
  cancelButton: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  cancelText: {
    ...typography.label,
    color: colors.heatCore,
  },
  progressText: {
    ...typography.bodySm,
    color: colors.inkSecondary,
    marginBottom: spacing.xs,
  },
  trackBackground: {
    backgroundColor: colors.void,
    borderRadius: rounded.pill,
    height: 8,
    overflow: 'hidden',
    width: '100%',
  },
  trackFill: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.pill,
    height: '100%',
  },
  errorText: {
    ...typography.bodySm,
    color: colors.heatCore,
  },
});
