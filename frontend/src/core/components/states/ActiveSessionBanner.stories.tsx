import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { ActiveSessionBanner } from './ActiveSessionBanner';

const meta = {
  title: 'States/ActiveSessionBanner',
  component: ActiveSessionBanner,
  args: {
    sessionId: 'session-123',
    onResumePress: fn(),
  },
} satisfies Meta<typeof ActiveSessionBanner>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    activityId: 'Running',
    durationSeconds: 720,
  },
};

export const LongDuration: Story = {
  args: {
    activityId: 'Cycling',
    durationSeconds: 5400,
  },
};

/** No duration yet reported for the in-progress session. */
export const NoDuration: Story = {
  args: {
    activityId: 'Workout',
  },
};
