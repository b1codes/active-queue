import React from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from '../../../core/components/Text';
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

  const estimateLabel = estimatedTotal ? `${estimatedTotal}` : '1,000+';

  return (
    <View style={styles.outerWrapper}>
      {/* The status and the Cancel button are siblings, not parent and child: an accessible
          wrapper would make VoiceOver read the summary and never reach Cancel. */}
      <View style={styles.container}>
        <View style={styles.headerRow}>
          <View
            style={styles.status}
            accessible={true}
            {...(error
              ? {
                  accessibilityRole: 'alert' as const,
                  accessibilityLabel: `Sync error: ${error}`,
                }
              : {
                  accessibilityRole: 'progressbar' as const,
                  accessibilityLabel: 'Syncing content source',
                  accessibilityValue: {
                    min: 0,
                    max: 100,
                    now: progressPercent,
                    text: `${itemsSyncedTotal} of about ${estimateLabel} items synced`,
                  },
                })}
          >
            <Text style={styles.titleText}>
              {isSyncing ? 'Syncing Content Source...' : 'Sync Status'}
            </Text>
            {error ? (
              <Text style={styles.errorText}>{error}</Text>
            ) : (
              <>
                <Text style={styles.progressText}>
                  {itemsSyncedTotal} of ~{estimateLabel} items synced
                </Text>
                <View style={styles.trackBackground}>
                  <View style={[styles.trackFill, { width: `${progressPercent}%` }]} />
                </View>
              </>
            )}
          </View>
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
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: spacing.sm,
  },
  status: {
    flex: 1,
    gap: spacing.xs,
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
    color: colors.heatCoreInk,
  },
  progressText: {
    ...typography.bodySm,
    color: colors.inkSecondary,
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
    color: colors.heatCoreInk,
  },
});
