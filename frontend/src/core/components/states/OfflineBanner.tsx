import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../theme';

interface OfflineBannerProps {
  onRetryPress?: () => void;
}

export const OfflineBanner: React.FC<OfflineBannerProps> = ({ onRetryPress }) => {
  return (
    <View
      style={styles.banner}
      accessible={true}
      accessibilityLabel="Network connection offline. Browsing cached feed mode."
    >
      <View style={styles.contentRow}>
        <Text style={styles.icon}>📡</Text>
        <View style={styles.textContainer}>
          <Text style={styles.title}>Network Connection Offline</Text>
          <Text style={styles.body}>
            You are browsing cached queue items. New syncs and session updates will resume automatically
            once reconnected.
          </Text>
        </View>

        {onRetryPress ? (
          <TouchableOpacity
            style={styles.retryButton}
            onPress={onRetryPress}
            activeOpacity={0.8}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Retry network connection"
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  banner: {
    backgroundColor: 'rgba(255, 69, 58, 0.12)',
    borderColor: 'rgba(255, 69, 58, 0.4)',
    borderRadius: rounded.md,
    borderWidth: 1,
    marginHorizontal: spacing.lg,
    marginVertical: spacing.sm,
    padding: spacing.md,
  },
  contentRow: {
    alignItems: 'center',
    flexDirection: 'row',
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
    color: '#FF6B6B',
    fontWeight: 'bold',
    marginBottom: 2,
  },
  body: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 12,
    lineHeight: 16,
  },
  retryButton: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.xs,
    borderWidth: 1,
    marginLeft: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  retryButtonText: {
    ...typography.label,
    color: colors.ink,
    fontSize: 12,
  },
});
