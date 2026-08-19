import type { Meta, StoryObj } from '@storybook/react-native';
import { ProviderQuotaBanner } from './ProviderQuotaBanner';

const meta = {
  title: 'States/ProviderQuotaBanner',
  component: ProviderQuotaBanner,
} satisfies Meta<typeof ProviderQuotaBanner>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Takes no props — shown whenever the YouTube API daily quota is reached. */
export const Default: Story = {};
