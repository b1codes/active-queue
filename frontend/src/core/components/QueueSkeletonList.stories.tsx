import type { Meta, StoryObj } from '@storybook/react-native';
import { QueueSkeletonList } from './ChromaticPulse';

const meta = {
  title: 'Core/QueueSkeletonList',
  component: QueueSkeletonList,
} satisfies Meta<typeof QueueSkeletonList>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Shown on the queue screen while the initial feed fetch is in flight. */
export const Default: Story = {
  args: { count: 4 },
};

export const SingleRow: Story = {
  args: { count: 1 },
};
