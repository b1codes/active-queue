import React from 'react';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, typography } from '@/core/theme';

export default function AppLayout() {
  const insets = useSafeAreaInsets();
  const bottomInset = Math.max(insets.bottom, 8);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.heatCore,
        tabBarInactiveTintColor: colors.inkFaint,
        tabBarStyle: {
          backgroundColor: colors.lensFlat,
          borderTopColor: colors.glassEdge,
          height: 52 + bottomInset,
          paddingBottom: bottomInset,
          paddingTop: 6,
        },
        tabBarLabelStyle: {
          ...typography.label,
          fontSize: 11,
          fontWeight: '600',
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
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'layers' : 'layers-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="blocks"
        options={{
          title: 'Time Blocks',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'time' : 'time-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'stats-chart' : 'stats-chart-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'settings' : 'settings-outline'} size={22} color={color} />
          ),
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
