import type { Preview } from '@storybook/react-native';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { Provider } from 'react-redux';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { store } from '../src/store';
import { colors } from '../src/core/theme';

/**
 * Mirrors app/_layout.tsx's provider stack exactly (GestureHandlerRootView >
 * Redux Provider > SafeAreaProvider) so components that depend on gesture
 * handling, Redux state (useQueueStore), or safe-area insets render the same
 * way here as they do in the real app — no story-specific mocking required.
 */
const preview: Preview = {
  decorators: [
    (Story) => (
      <GestureHandlerRootView style={styles.root}>
        <Provider store={store}>
          <SafeAreaProvider>
            <View style={styles.canvas}>
              <Story />
            </View>
          </SafeAreaProvider>
        </Provider>
      </GestureHandlerRootView>
    ),
  ],

  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
  },
};

export default preview;

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  // App is dark-only (app.json userInterfaceStyle) — the void ground is the
  // real backdrop every glass/lens surface composites against.
  canvas: {
    flex: 1,
    backgroundColor: colors.void,
  },
});
