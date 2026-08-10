import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../theme';

interface DeepLinkFailedCardProps {
  appName: string;
  onRetryPress: () => void;
  onManualOpenPress?: () => void;
}

export const DeepLinkFailedCard: React.FC<DeepLinkFailedCardProps> = ({
  appName,
  onRetryPress,
  onManualOpenPress,
}) => {
  return (
    <View
      style={styles.card}
      accessible={true}
      accessibilityLabel={`Unable to launch ${appName}. Your workout session state is unchanged.`}
    >
      <View style={styles.headerRow}>
        <Text style={styles.icon}>🔗</Text>
        <Text style={styles.title}>Unable to Open {appName}</Text>
      </View>

      <Text style={styles.body}>
        We couldn't automatically open {appName}. Your active workout session remains safely in
        progress.
      </Text>

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={onRetryPress}
          activeOpacity={0.8}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel={`Retry launching ${appName}`}
        >
          <Text style={styles.primaryButtonText}>Retry Launch</Text>
        </TouchableOpacity>

        {onManualOpenPress ? (
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={onManualOpenPress}
            activeOpacity={0.8}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Open in Web Browser"
          >
            <Text style={styles.secondaryButtonText}>Open in Browser</Text>
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
    marginVertical: spacing.md,
    padding: spacing.lg,
  },
  headerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: spacing.xs,
  },
  icon: {
    fontSize: 20,
    marginRight: spacing.xs,
  },
  title: {
    ...typography.label,
    color: colors.ink,
    fontSize: 16,
    fontWeight: 'bold',
  },
  body: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 14,
    marginBottom: spacing.md,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.sm,
    flex: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.md,
  },
  primaryButtonText: {
    ...typography.label,
    color: colors.void,
    fontWeight: 'bold',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    flex: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.md,
  },
  secondaryButtonText: {
    ...typography.label,
    color: colors.ink,
  },
});
