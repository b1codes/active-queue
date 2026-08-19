import type { Meta, StoryObj } from '@storybook/react-native';
import { FeedCard } from './FeedCard';
import { FeedItem } from '../types';

const baseItem: FeedItem = {
  id: 'feed-1',
  content_id: 'content-1',
  source_id: 'source-1',
  title: 'Full Body HIIT Workout — No Equipment Needed',
  provider: 'youtube',
  external_id: 'dQw4w9WgXcQ',
  duration_seconds: 1830,
  duration_label: '30:30',
  published_at: '2026-08-01T12:00:00Z',
  thumbnail_url: 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
  video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  consumed: false,
};

const meta = {
  title: 'Queue/FeedCard',
  component: FeedCard,
  args: {
    item: baseItem,
  },
} satisfies Meta<typeof FeedCard>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

/** Duration matched to the active workout window — Void ink on Heat Core fill. */
export const Matched: Story = {
  args: {
    isMatched: true,
  },
};

export const NoThumbnail: Story = {
  args: {
    item: { ...baseItem, thumbnail_url: null },
  },
};

export const LongTitle: Story = {
  args: {
    item: {
      ...baseItem,
      title:
        '45-Minute Advanced Kettlebell & Dumbbell Strength Circuit for Full Body Conditioning',
    },
  },
};

export const ShortDuration: Story = {
  args: {
    item: { ...baseItem, duration_seconds: 245, duration_label: '4:05' },
  },
};
