import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { WatchLaterRejectedState } from './WatchLaterRejectedState';

const meta = {
  title: 'States/WatchLaterRejectedState',
  component: WatchLaterRejectedState,
  args: {
    onDismissPress: fn(),
  },
} satisfies Meta<typeof WatchLaterRejectedState>;

export default meta;

type Story = StoryObj<typeof meta>;

/**
 * Rendered inside AddSourceModal in place of the URL form whenever the
 * pasted URL resolves to YouTube's "Watch Later" system playlist.
 */
export const WithGuide: Story = {
  args: { onCreateCustomGuidePress: fn() },
};

export const WithoutGuide: Story = {};
