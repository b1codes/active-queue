import type { Meta, StoryObj } from '@storybook/react-native';
import React, { useEffect } from 'react';
import { fn } from 'storybook/test';
import { AddSourceModal } from './AddSourceModal';
import { useQueueStore } from '../queueStore';

/**
 * AddSourceModal reads isAddingSource/addSourceError from Redux rather than
 * taking them as props, so this wrapper seeds that slice before mount to
 * drive the submitting/error variants, and resets it on unmount.
 */
function SeededAddSourceModal({
  isAddingSource,
  addSourceError,
  ...modalProps
}: React.ComponentProps<typeof AddSourceModal> & {
  isAddingSource?: boolean;
  addSourceError?: string | null;
}) {
  useEffect(() => {
    useQueueStore.setState({
      isAddingSource: isAddingSource ?? false,
      addSourceError: addSourceError ?? null,
    });
    return () => {
      useQueueStore.setState({ isAddingSource: false, addSourceError: null });
    };
  }, [isAddingSource, addSourceError]);

  return <AddSourceModal {...modalProps} />;
}

const meta = {
  title: 'Queue/AddSourceModal',
  component: SeededAddSourceModal,
  args: {
    visible: true,
    onClose: fn(),
  },
} satisfies Meta<typeof SeededAddSourceModal>;

export default meta;

type Story = StoryObj<typeof meta>;

/** Empty URL input, ready for entry. */
export const Default: Story = {};

/** Submit in flight — the Add Source button shows a spinner and disables. */
export const Submitting: Story = {
  args: {
    isAddingSource: true,
  },
};

/** A rejected URL, e.g. an unreachable or private playlist. */
export const WithError: Story = {
  args: {
    addSourceError: 'Playlist not found or is private.',
  },
};

/** Pasted URL resolved to YouTube's restricted "Watch Later" system playlist. */
export const WatchLaterRejected: Story = {
  args: {
    addSourceError: 'SOURCE_UNSUPPORTED: Watch Later is a system playlist and cannot be synced.',
  },
};
