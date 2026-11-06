import React from 'react';
import { AccessibilityInfo } from 'react-native';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import {
  ActiveSessionBanner,
  DeepLinkFailedCard,
  EmptyFeedState,
  NoDurationMatchState,
  NoSourcesState,
  OfflineBanner,
  ProviderQuotaBanner,
  SyncResumableCard,
  WatchLaterRejectedState,
} from '@/core/components/states';

describe('ActiveSessionBanner', () => {
  it('describes the session and resumes it by id', async () => {
    const onResume = jest.fn();
    await render(
      <ActiveSessionBanner sessionId="s_1" activityId="running" durationSeconds={1800} onResumePress={onResume} />
    );
    const button = screen.getByRole('button', { name: /RUNNING 30m/ });
    await fireEvent.press(button);
    expect(onResume).toHaveBeenCalledWith('s_1');
  });

  it('copes with missing duration and follows Reduce Motion changes', async () => {
    let listener: ((enabled: boolean) => void) | undefined;
    const remove = jest.fn();
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
    jest.spyOn(AccessibilityInfo, 'addEventListener').mockImplementation(((_: string, cb: (e: boolean) => void) => {
      listener = cb;
      return { remove };
    }) as never);
    const { unmount } = await render(<ActiveSessionBanner sessionId="s_1" onResumePress={jest.fn()} />);
    expect(screen.getByRole('button', { name: /WORKOUT \. Tap to resume/ })).toBeTruthy();
    await act(async () => listener?.(false));
    await unmount();
    expect(remove).toHaveBeenCalled();
  });
});

describe('DeepLinkFailedCard', () => {
  it('offers retry and a browser fallback', async () => {
    const onRetry = jest.fn();
    const onManual = jest.fn();
    await render(<DeepLinkFailedCard appName="YouTube" onRetryPress={onRetry} onManualOpenPress={onManual} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Retry launching YouTube' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Open in Web Browser' }));
    expect(onRetry).toHaveBeenCalled();
    expect(onManual).toHaveBeenCalled();
  });

  it('hides the browser option when there is no fallback', async () => {
    await render(<DeepLinkFailedCard appName="Strava" onRetryPress={jest.fn()} />);
    expect(screen.queryByRole('button', { name: 'Open in Web Browser' })).toBeNull();
  });
});

describe('EmptyFeedState', () => {
  it('offers sync and add-source actions only when handlers exist', async () => {
    const onSync = jest.fn();
    const onAdd = jest.fn();
    const { rerender } = await render(<EmptyFeedState onSyncPress={onSync} onAddSourcePress={onAdd} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Sync sources now' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Add another content source' }));
    expect(onSync).toHaveBeenCalled();
    expect(onAdd).toHaveBeenCalled();
    await rerender(<EmptyFeedState />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('NoDurationMatchState', () => {
  it.each([
    ['duration_out_of_range', /between 5 minutes/],
    ['no_matching_activity', /No activity in the catalog/],
    ['no_content_in_window', /primary \[B, B\+5m\]/],
    [undefined, /No workout items match/],
  ])('explains %s', async (reason, text) => {
    await render(<NoDurationMatchState durationLabel="45:00" rejectionReason={reason} />);
    expect(screen.getByLabelText(text)).toBeTruthy();
  });

  it('shows the target and a reset action', async () => {
    const onReset = jest.fn();
    await render(<NoDurationMatchState durationLabel="45:00" onResetPress={onReset} />);
    expect(screen.getByText('Target: 45:00')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Try a different duration' }));
    expect(onReset).toHaveBeenCalled();
  });
});

describe('NoSourcesState', () => {
  it('prompts to add the first playlist', async () => {
    const onAdd = jest.fn();
    await render(<NoSourcesState onAddSourcePress={onAdd} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Add first playlist source' }));
    expect(onAdd).toHaveBeenCalled();
  });
});

describe('OfflineBanner', () => {
  it('retries when asked and hides retry without a handler', async () => {
    const onRetry = jest.fn();
    const { rerender } = await render(<OfflineBanner onRetryPress={onRetry} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Retry network connection' }));
    expect(onRetry).toHaveBeenCalled();
    await rerender(<OfflineBanner />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('ProviderQuotaBanner', () => {
  it('explains that the cached queue still works', async () => {
    await render(<ProviderQuotaBanner />);
    expect(screen.getByLabelText(/existing cached queue remains available/)).toBeTruthy();
  });
});

describe('SyncResumableCard', () => {
  it('finishes or dismisses the sync', async () => {
    const onFinish = jest.fn();
    const onDismiss = jest.fn();
    await render(<SyncResumableCard sourceTitle="Morning Runs" onFinishSyncPress={onFinish} onDismissPress={onDismiss} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Finish syncing Morning Runs' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Dismiss sync prompt' }));
    expect(onFinish).toHaveBeenCalled();
    expect(onDismiss).toHaveBeenCalled();
  });
});

describe('WatchLaterRejectedState', () => {
  it('dismisses and optionally opens the guide', async () => {
    const onDismiss = jest.fn();
    const onGuide = jest.fn();
    const { rerender } = await render(
      <WatchLaterRejectedState onDismissPress={onDismiss} onCreateCustomGuidePress={onGuide} />
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Got it, try another URL' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Learn more about YouTube playlists' }));
    expect(onDismiss).toHaveBeenCalled();
    expect(onGuide).toHaveBeenCalled();
    await rerender(<WatchLaterRejectedState onDismissPress={onDismiss} />);
    expect(screen.queryByRole('button', { name: 'Learn more about YouTube playlists' })).toBeNull();
  });
});
