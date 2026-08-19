import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { OfflineBanner } from './OfflineBanner';

const meta = {
  title: 'States/OfflineBanner',
  component: OfflineBanner,
} satisfies Meta<typeof OfflineBanner>;

export default meta;

type Story = StoryObj<typeof meta>;

export const WithRetry: Story = {
  args: { onRetryPress: fn() },
};

export const WithoutRetry: Story = {};
