import React from 'react';
import { Tabs } from 'expo-router';
import { colors, typography } from '@/core/theme';

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.heatCore,
        tabBarInactiveTintColor: colors.inkFaint,
        tabBarStyle: {
          backgroundColor: colors.lensFlat,
          borderTopColor: colors.glassEdge,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          ...typography.label,
        },
        sceneStyle: {
          backgroundColor: colors.void,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Queue',
        }}
      />
      <Tabs.Screen
        name="blocks"
        options={{
          title: 'Time Blocks',
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
        }}
      />
      <Tabs.Screen
        name="match/[contentId]"
        options={{
          href: null,
        }}
      />
      <Tabs.Screen
        name="session/[id]"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}
