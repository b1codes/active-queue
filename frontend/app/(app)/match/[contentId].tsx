import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { colors, typography, spacing } from '@/core/theme';

export default function MatchScreen() {
  const { contentId } = useLocalSearchParams<{ contentId: string }>();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Match Activity</Text>
      <Text style={styles.subtitle}>Content ID: {contentId}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.void,
    paddingTop: spacing.xxl,
    paddingHorizontal: spacing.lg,
  },
  title: {
    ...typography.headline,
    color: colors.ink,
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.body,
    color: colors.inkMuted,
  },
});
