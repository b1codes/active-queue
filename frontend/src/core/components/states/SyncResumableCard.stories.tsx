import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { SyncResumableCard } from './SyncResumableCard';

const meta = {
  title: 'States/SyncResumableCard',
  component: SyncResumableCard,
  args: {
    sourceTitle: 'My Workout Queue',
    onFinishSyncPress: fn(),
  },
} satisfies Meta<typeof SyncResumableCard>;

export default meta;

type Story = StoryObj<typeof meta>;

export const WithDismiss: Story = {
  args: { onDismissPress: fn() },
};

export const WithoutDismiss: Story = {};
