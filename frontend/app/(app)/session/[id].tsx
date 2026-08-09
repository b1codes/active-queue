import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { colors, typography, spacing } from '@/core/theme';

export default function SessionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Handoff Checklist</Text>
      <Text style={styles.subtitle}>Session ID: {id}</Text>
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
