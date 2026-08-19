import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { NoDurationMatchState } from './NoDurationMatchState';

const meta = {
  title: 'States/NoDurationMatchState',
  component: NoDurationMatchState,
  args: {
    durationLabel: '30m',
    onResetPress: fn(),
  },
} satisfies Meta<typeof NoDurationMatchState>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Generic: Story = {};

export const DurationOutOfRange: Story = {
  args: { rejectionReason: 'duration_out_of_range' },
};

export const NoMatchingActivity: Story = {
  args: { rejectionReason: 'no_matching_activity' },
};

export const NoContentInWindow: Story = {
  args: { rejectionReason: 'no_content_in_window' },
};
