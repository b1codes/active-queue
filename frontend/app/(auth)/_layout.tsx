import React from 'react';
import { Stack } from 'expo-router';
import { colors } from '@/core/theme';

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.void },
      }}
    >
      <Stack.Screen name="sign-in" />
    </Stack>
  );
}
