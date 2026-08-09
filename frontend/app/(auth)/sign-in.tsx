import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, spacing } from '@/core/theme';

export default function SignInScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>ActiveQueue</Text>
      <Text style={styles.subtitle}>Sign in to access your media queue</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.void,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  title: {
    ...typography.display,
    color: colors.ink,
    marginBottom: spacing.sm,
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    textAlign: 'center',
  },
});
