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
    <View style={styles.outerWrapper}>
      <View
        style={styles.container}
        accessible={true}
        accessibilityLabel={
          error
            ? `Sync error: ${error}`
            : `Syncing content: ${itemsSyncedTotal} of estimated ${estimatedTotal || 1000} items synced (${progressPercent} percent)`
        }
      >
        <View style={styles.headerRow}>
          <Text style={styles.titleText}>
            {isSyncing ? 'Syncing Content Source...' : 'Sync Status'}
          </Text>
          {isSyncing && (
            <TouchableOpacity
              onPress={cancelSync}
              style={styles.cancelButton}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Cancel content sync"
            >
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
  container: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
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
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: spacing.sm,
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
