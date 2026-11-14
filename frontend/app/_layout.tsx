import React, { useEffect } from "react";
import { View, StyleSheet } from "react-native";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Provider } from "react-redux";
import { store } from "@/store";
import { ChromaticPulse } from "@/core/components";
import { colors, rounded } from "@/core/theme";
import { useAuthStore } from "@/features/auth/authStore";

import { GestureHandlerRootView } from "react-native-gesture-handler";

function AppNavigation() {
  const { initAuth, isAuthenticated, isLoading } = useAuthStore();

  useEffect(() => {
    const unsubscribe = initAuth();
    return () => unsubscribe();
  }, [initAuth]);

  if (isLoading) {
    return (
      <SafeAreaProvider>
        <View style={styles.loadingContainer}>
          <ChromaticPulse style={{ width: 140, height: 6, borderRadius: rounded.pill }} />
        </View>
      </SafeAreaProvider>
    );
  }


  return (
    <SafeAreaProvider>
      <StatusBar style="light" backgroundColor={colors.void} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.void },
        }}
      >
        {/* Only the group a user may be in is registered, so a signed-out launch never
            mounts the queue (it used to, fetching with no token before a redirect), and
            signing in or out moves to the other group. */}
        <Stack.Protected guard={!isAuthenticated}>
          <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        </Stack.Protected>
        <Stack.Protected guard={isAuthenticated}>
          <Stack.Screen name="(app)" options={{ headerShown: false }} />
        </Stack.Protected>
      </Stack>
    </SafeAreaProvider>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={styles.rootView}>
      <Provider store={store}>
        <AppNavigation />
      </Provider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  rootView: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.void,
    justifyContent: "center",
    alignItems: "center",
  },
});
