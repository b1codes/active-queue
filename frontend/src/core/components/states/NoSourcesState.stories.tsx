import type { Meta, StoryObj } from '@storybook/react-native';
import { fn } from 'storybook/test';
import { NoSourcesState } from './NoSourcesState';

const meta = {
  title: 'States/NoSourcesState',
  component: NoSourcesState,
  args: {
    onAddSourcePress: fn(),
  },
} satisfies Meta<typeof NoSourcesState>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Shown on the queue screen when the user has never added a content source. */
export const Default: Story = {};
