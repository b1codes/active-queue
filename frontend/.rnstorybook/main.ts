import type { StorybookConfig } from '@storybook/react-native';

const main: StorybookConfig = {
  // Stories live next to the real component they cover, under src/ — there is no
  // separate example component tree to keep in sync with the app.
  stories: ['../src/**/*.stories.?(ts|tsx|js|jsx)'],
  deviceAddons: ['@storybook/addon-ondevice-controls', '@storybook/addon-ondevice-actions'],
};

export default main;
