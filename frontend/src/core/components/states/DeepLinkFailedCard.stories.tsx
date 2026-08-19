import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { DeepLinkFailedCard } from './DeepLinkFailedCard';

const meta = {
  title: 'States/DeepLinkFailedCard',
  component: DeepLinkFailedCard,
  args: {
    appName: 'Strava',
    onRetryPress: fn(),
  },
} satisfies Meta<typeof DeepLinkFailedCard>;

export default meta;

type Story = StoryObj<typeof meta>;

export const WithManualOpen: Story = {
  args: { onManualOpenPress: fn() },
};

export const RetryOnly: Story = {};

export const YouTube: Story = {
  args: { appName: 'YouTube', onManualOpenPress: fn() },
};
