import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, rounded, spacing, typography } from '../../theme';

interface EmptyFeedStateProps {
  onSyncPress?: () => void;
  onAddSourcePress?: () => void;
}

export const EmptyFeedState: React.FC<EmptyFeedStateProps> = ({
  onSyncPress,
  onAddSourcePress,
}) => {
  return (
    <View
      style={styles.container}
      accessible={true}
      accessibilityLabel="You are all caught up. No unconsumed feed items available."
    >
      <View style={styles.cardWrapper}>
        <View style={styles.iconBadge}>
          <Ionicons name="sparkles-outline" size={30} color={colors.heatCore} />
        </View>

        <Text style={styles.title}>You're All Caught Up!</Text>
        <Text style={styles.subtitle}>
          All content items in your sources have been completed or marked consumed.
        </Text>

        <View style={styles.buttonRow}>
          {onSyncPress ? (
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={onSyncPress}
              activeOpacity={0.8}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Sync sources now"
            >
              <Text style={styles.primaryButtonText}>Sync Sources Now</Text>
            </TouchableOpacity>
          ) : null}

          {onAddSourcePress ? (
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={onAddSourcePress}
              activeOpacity={0.8}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Add another content source"
            >
              <Text style={styles.secondaryButtonText}>+ Add Source</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    backgroundColor: colors.void,
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxl,
  },
  cardWrapper: {
    alignItems: 'center',
    maxWidth: 480,
    width: '100%',
  },
  iconBadge: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.lg,
    borderWidth: 1,
    height: 64,
    justifyContent: 'center',
    marginBottom: spacing.md,
    width: 64,
  },
  title: {
    ...typography.title,
    color: colors.ink,
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    marginBottom: spacing.xl,
    textAlign: 'center',
  },
  buttonRow: {
    gap: spacing.sm,
    width: '100%',
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.md,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    width: '100%',
  },
  primaryButtonText: {
    ...typography.label,
    color: colors.void,
    fontSize: 16,
    fontWeight: 'bold',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    width: '100%',
  },
  secondaryButtonText: {
    ...typography.label,
    color: colors.ink,
    fontSize: 16,
  },
});
