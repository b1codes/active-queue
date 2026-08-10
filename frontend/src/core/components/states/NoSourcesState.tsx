import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, rounded, spacing, typography } from '../../theme';


interface NoSourcesStateProps {
  onAddSourcePress: () => void;
}

export const NoSourcesState: React.FC<NoSourcesStateProps> = ({ onAddSourcePress }) => {
  return (
    <View
      style={styles.container}
      accessible={true}
      accessibilityLabel="No content sources added yet. Learn how to add a playlist."
    >
      <View style={styles.iconBadge}>
        <Ionicons name="tv-outline" size={30} color={colors.inkFaint} />
      </View>


      <Text style={styles.title}>No Content Sources Added</Text>
      <Text style={styles.description}>
        ActiveQueue syncs videos from public YouTube playlists to build your workout queue.
      </Text>

      <View style={styles.infoBox}>
        <Text style={styles.infoTitle}>💡 Why can't I use Watch Later?</Text>
        <Text style={styles.infoBody}>
          Google restricted YouTube API access to private "Watch Later" and "Liked Videos"
          system playlists. To use ActiveQueue, simply create a new custom playlist on YouTube
          and paste its URL here!
        </Text>
      </View>

      <TouchableOpacity
        style={styles.button}
        onPress={onAddSourcePress}
        activeOpacity={0.8}
        accessible={true}
        accessibilityRole="button"
        accessibilityLabel="Add first playlist source"
        accessibilityHint="Opens modal to enter YouTube playlist URL"
      >
        <Text style={styles.buttonText}>+ Add First Source</Text>
      </TouchableOpacity>
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
  iconText: {
    fontSize: 32,
  },
  title: {
    ...typography.title,
    color: colors.ink,
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  description: {
    ...typography.body,
    color: colors.inkSecondary,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  infoBox: {
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    marginBottom: spacing.xl,
    padding: spacing.md,
    width: '100%',
  },
  infoTitle: {
    ...typography.label,
    color: colors.heatCore,
    marginBottom: spacing.xs,
  },
  infoBody: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.md,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    width: '100%',
  },
  buttonText: {
    ...typography.label,
    color: colors.void,
    fontSize: 16,
    fontWeight: 'bold',
  },
});
