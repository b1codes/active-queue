import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../theme';

interface SyncResumableCardProps {
  sourceTitle: string;
  onFinishSyncPress: () => void;
  onDismissPress?: () => void;
}

export const SyncResumableCard: React.FC<SyncResumableCardProps> = ({
  sourceTitle,
  onFinishSyncPress,
  onDismissPress,
}) => {
  return (
    <View
      style={styles.card}
      accessible={true}
      accessibilityLabel={`Sync incomplete for ${sourceTitle}. Tap to finish syncing items.`}
    >
      <View style={styles.contentRow}>
        <Text style={styles.icon}>⚡</Text>
        <View style={styles.textContainer}>
          <Text style={styles.title}>Resume Playlist Sync</Text>
          <Text style={styles.body} numberOfLines={2}>
            Finish syncing items for "{sourceTitle}"
          </Text>
        </View>
      </View>

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={onFinishSyncPress}
          activeOpacity={0.8}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel={`Finish syncing ${sourceTitle}`}
        >
          <Text style={styles.primaryButtonText}>Finish Syncing</Text>
        </TouchableOpacity>

        {onDismissPress ? (
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={onDismissPress}
            activeOpacity={0.8}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Dismiss sync prompt"
          >
            <Text style={styles.secondaryButtonText}>Later</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.substrate,
    borderColor: colors.heatCore,
    borderRadius: rounded.md,
    borderWidth: 1,
    marginHorizontal: spacing.lg,
    marginVertical: spacing.sm,
    padding: spacing.md,
  },
  contentRow: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: spacing.sm,
  },
  icon: {
    fontSize: 20,
    marginRight: spacing.sm,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    ...typography.label,
    color: colors.heatCore,
    fontSize: 14,
    fontWeight: 'bold',
  },
  body: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 12,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.xs,
    flex: 1,
    justifyContent: 'center',
    minHeight: 40,
  },
  primaryButtonText: {
    ...typography.label,
    color: colors.void,
    fontSize: 13,
    fontWeight: 'bold',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderRadius: rounded.xs,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 40,
    paddingHorizontal: spacing.md,
  },
  secondaryButtonText: {
    ...typography.label,
    color: colors.inkSecondary,
    fontSize: 13,
  },
});
