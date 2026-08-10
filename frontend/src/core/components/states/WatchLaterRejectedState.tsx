import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../theme';

interface WatchLaterRejectedStateProps {
  onDismissPress: () => void;
  onCreateCustomGuidePress?: () => void;
}

export const WatchLaterRejectedState: React.FC<WatchLaterRejectedStateProps> = ({
  onDismissPress,
  onCreateCustomGuidePress,
}) => {
  return (
    <View
      style={styles.card}
      accessible={true}
      accessibilityLabel="Watch Later system playlist cannot be synced due to YouTube API platform restrictions. Create a custom YouTube playlist instead."
    >
      <View style={styles.headerRow}>
        <Text style={styles.icon}>🚫</Text>
        <Text style={styles.title}>System Playlist Restricted</Text>
      </View>

      <Text style={styles.body}>
        Google removed API access to private "Watch Later", "Liked Videos", and "History" playlists.
        ActiveQueue cannot import these system playlists directly.
      </Text>

      <View style={styles.solutionBox}>
        <Text style={styles.solutionTitle}>How to fix this in 30 seconds:</Text>
        <Text style={styles.solutionStep}>1. Open YouTube app or web</Text>
        <Text style={styles.solutionStep}>2. Create a new custom playlist (e.g. "My Workout Queue")</Text>
        <Text style={styles.solutionStep}>3. Add your videos and paste the new playlist link here!</Text>
      </View>

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={onDismissPress}
          activeOpacity={0.8}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel="Got it, try another URL"
        >
          <Text style={styles.primaryButtonText}>Got It, Try Another URL</Text>
        </TouchableOpacity>

        {onCreateCustomGuidePress ? (
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={onCreateCustomGuidePress}
            activeOpacity={0.8}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Learn more about YouTube playlists"
          >
            <Text style={styles.secondaryButtonText}>Guide</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.strata,
    borderColor: colors.heatCore,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.lg,
    width: '100%',
  },
  headerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: spacing.xs,
  },
  icon: {
    fontSize: 22,
    marginRight: spacing.xs,
  },
  title: {
    ...typography.label,
    color: colors.heatCore,
    fontSize: 16,
    fontWeight: 'bold',
  },
  body: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: spacing.md,
  },
  solutionBox: {
    backgroundColor: colors.substrate,
    borderRadius: rounded.sm,
    marginBottom: spacing.lg,
    padding: spacing.md,
  },
  solutionTitle: {
    ...typography.label,
    color: colors.ink,
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: spacing.xs,
  },
  solutionStep: {
    ...typography.bodySm,
    color: colors.inkSecondary,
    fontSize: 12,
    marginBottom: 2,
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
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.lg,
  },
  secondaryButtonText: {
    ...typography.label,
    color: colors.ink,
  },
});
