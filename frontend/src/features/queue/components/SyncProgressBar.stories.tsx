import type { Meta, StoryObj } from '@storybook/react-native';
import React, { useEffect } from 'react';
import { SyncProgressBar } from './SyncProgressBar';
import { useQueueStore } from '../queueStore';
import { INITIAL_SYNC_STATE } from '../queueSlice';
import { SyncProgressState } from '../types';

/**
 * SyncProgressBar takes no props — it reads syncProgress straight out of
 * Redux and renders null when idle. This wrapper seeds that slice before
 * mount so each story can drive a specific progress state, then resets it
 * on unmount so stories don't bleed state into one another.
 */
function SeededSyncProgressBar({ syncProgress }: { syncProgress: Partial<SyncProgressState> }) {
  useEffect(() => {
    useQueueStore.setState({ syncProgress: { ...INITIAL_SYNC_STATE, ...syncProgress } });
    return () => {
      useQueueStore.setState({ syncProgress: INITIAL_SYNC_STATE });
    };
  }, [syncProgress]);

  return <SyncProgressBar />;
}

const meta = {
  title: 'Queue/SyncProgressBar',
  component: SeededSyncProgressBar,
} satisfies Meta<typeof SeededSyncProgressBar>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Syncing: Story = {
  args: {
    syncProgress: { isSyncing: true, itemsSyncedTotal: 240, estimatedTotal: 1000 },
  },
};

export const NearlyDone: Story = {
  args: {
    syncProgress: { isSyncing: true, itemsSyncedTotal: 940, estimatedTotal: 1000 },
  },
};

/** 40-iteration guardrail tripped (SPEC §9.4). */
export const ErrorState: Story = {
  args: {
    syncProgress: { isSyncing: false, error: 'Sync iteration limit reached (40 chunks)' },
  },
};

/** No estimated total yet — falls back to the "1,000+" label. */
export const UnknownTotal: Story = {
  args: {
    syncProgress: { isSyncing: true, itemsSyncedTotal: 60, estimatedTotal: null },
  },
};
