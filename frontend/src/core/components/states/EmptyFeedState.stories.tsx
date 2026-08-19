import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { EmptyFeedState } from './EmptyFeedState';

const meta = {
  title: 'States/EmptyFeedState',
  component: EmptyFeedState,
} satisfies Meta<typeof EmptyFeedState>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Both actions shown, as rendered when the feed list is empty but sources exist. */
export const Default: Story = {
  args: {
    onSyncPress: fn(),
    onAddSourcePress: fn(),
  },
};

export const SyncOnly: Story = {
  args: {
    onSyncPress: fn(),
  },
};

export const AddSourceOnly: Story = {
  args: {
    onAddSourcePress: fn(),
  },
};
