import type { Meta, StoryObj } from '@storybook/react-native';
import { ChromaticPulse } from './ChromaticPulse';
import { colors } from '../theme';

const meta = {
  title: 'Core/ChromaticPulse',
  component: ChromaticPulse,
  args: {
    style: { width: 160, height: 16, borderRadius: 8 },
  },
} satisfies Meta<typeof ChromaticPulse>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Default ember cycle: Corona -> Core -> Ember -> Corona, 3200ms. */
export const Default: Story = {};

/** A caller-supplied palette, e.g. the "verified" signal cycle used elsewhere in the app. */
export const SignalPalette: Story = {
  args: {
    colors: [colors.signalVerified, colors.heatCorona, colors.emberDeep],
  },
};

/** Sized to match a single QueueSkeletonList thumbnail placeholder. */
export const ThumbnailSize: Story = {
  args: {
    style: { width: 104, height: 58.5, borderRadius: 6 },
  },
};
