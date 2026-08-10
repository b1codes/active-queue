import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../theme';

export const ProviderQuotaBanner: React.FC = () => {
  return (
    <View
      style={styles.banner}
      accessible={true}
      accessibilityLabel="YouTube API daily quota reached. New items are paused, but your existing cached queue remains available."
    >
      <View style={styles.contentRow}>
        <Text style={styles.icon}>⚠️</Text>
        <View style={styles.textContainer}>
          <Text style={styles.title}>YouTube API Quota Reached</Text>
          <Text style={styles.body}>
            New playlist syncs are temporarily paused until Google resets quota. Your existing
            cached queue is 100% browsable and ready for workouts!
          </Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  banner: {
    backgroundColor: 'rgba(255, 171, 0, 0.12)',
    borderColor: 'rgba(255, 171, 0, 0.4)',
    borderRadius: rounded.md,
    borderWidth: 1,
    marginHorizontal: spacing.lg,
    marginVertical: spacing.sm,
    padding: spacing.md,
  },
  contentRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
  },
  icon: {
    fontSize: 20,
    marginRight: spacing.sm,
    marginTop: 2,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    ...typography.label,
    color: '#FFD54F',
    fontWeight: 'bold',
    marginBottom: 2,
  },
  body: {
    ...typography.body,
    color: colors.inkSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
});
