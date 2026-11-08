import React from 'react';
import { Alert } from 'react-native';
import { act, fireEvent, screen } from '@testing-library/react-native';
import { FeedCard } from '@/features/queue/components/FeedCard';
import { AddSourceModal } from '@/features/queue/components/AddSourceModal';
import { SyncProgressBar } from '@/features/queue/components/SyncProgressBar';
import { useQueueStore } from '@/features/queue/queueStore';
import { feedItem, mockApi, renderWithProviders, resetStores, source } from '@/test-utils';

beforeEach(() => resetStores());

describe('FeedCard', () => {
  it('announces title, tabular duration and provider', async () => {
    await renderWithProviders(<FeedCard item={feedItem(1, { duration_seconds: 3725 })} />);
    expect(screen.getByRole('button', { name: /Fixture Workout Video #1, duration 1:02:05, from Fixture/ })).toBeTruthy();
    expect(screen.getByText('1:02:05')).toBeTruthy();
  });

  it.each([
    [0, '45:12', '45:12'],
    [0, '45m', '--:--'],
    [125, undefined, '2:05'],
  ])('formats duration %s / label %s as %s', async (seconds, label, expected) => {
    await renderWithProviders(
      <FeedCard item={feedItem(1, { duration_seconds: seconds, duration_label: label as string })} />
    );
    expect(screen.getByText(expected)).toBeTruthy();
  });

  it('falls back for missing title/provider and marks matched cards', async () => {
    await renderWithProviders(
      <FeedCard item={feedItem(1, { title: '', provider: '' })} isMatched={true} />
    );
    expect(screen.getByRole('button', { name: /Untitled Content.*from Source, duration matched/ })).toBeTruthy();
  });

  it('tap opens the item via onPress', async () => {
    const onPress = jest.fn();
    const item = feedItem(1);
    await renderWithProviders(<FeedCard item={item} onPress={onPress} />);
    await fireEvent(screen.getByTestId('feed-card-fx:fx_vid_1'), 'accessibilityAction', {
      nativeEvent: { actionName: 'activate' },
    });
    expect(onPress).toHaveBeenCalledWith(item);
  });

  it('the options menu hides the item (long-press has a button equivalent, SPEC §11.4)', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    useQueueStore.setState({ feedItems: [feedItem(1)], totalUnconsumed: 1 });
    const api = mockApi({ 'POST /api/v1/content/feed/fx:fx_vid_1/hide': { data: { hidden: true } } });
    await renderWithProviders(<FeedCard item={feedItem(1)} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Options for Fixture Workout Video #1' }));
    const buttons = alert.mock.calls[0][2]!;
    expect(buttons.map((b) => b.text)).toEqual(['Hide from Queue', 'Cancel']);
    await act(async () => buttons[0].onPress!());
    expect(api.calls).toHaveLength(1);
    expect(useQueueStore.getState().feedItems).toHaveLength(0);
  });
});

describe('AddSourceModal', () => {
  it('submits a trimmed URL, then closes on success', async () => {
    const onClose = jest.fn();
    const api = mockApi({
      'POST /api/v1/sources': { status: 201, data: source() },
      'POST /api/v1/sources/u1_fixture_pl/sync': { data: { items_synced: 0, has_more: false } },
      'GET /api/v1/content/feed': { data: { items: [], next_cursor: null, total_unconsumed: 0 } },
      'GET /api/v1/sources': { data: { items: [source()] } },
    });
    await renderWithProviders(<AddSourceModal visible={true} onClose={onClose} />);

    const add = screen.getByRole('button', { name: 'Add source' });
    expect(add.props.accessibilityState?.disabled).toBe(true);
    await fireEvent.changeText(screen.getByPlaceholderText(/youtube.com\/playlist/), '  PL123  ');
    await fireEvent.press(screen.getByRole('button', { name: 'Add source' }));
    expect(api.calls[0].body).toEqual({ url_or_id: 'PL123' });
    expect(onClose).toHaveBeenCalled();
  });

  it('shows the server error inline and keeps the modal open', async () => {
    const onClose = jest.fn();
    mockApi({
      'POST /api/v1/sources': { status: 409, error: { code: 'SOURCE_ALREADY_ADDED', message: 'Already added' } },
    });
    await renderWithProviders(<AddSourceModal visible={true} onClose={onClose} />);
    await fireEvent.changeText(screen.getByPlaceholderText(/youtube.com\/playlist/), 'PL1');
    await fireEvent.press(screen.getByRole('button', { name: 'Add source' }));
    expect(screen.getByText('Already added')).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
    // Typing clears the error.
    await fireEvent.changeText(screen.getByPlaceholderText(/youtube.com\/playlist/), 'PL2');
    expect(screen.queryByText('Already added')).toBeNull();
  });

  it('shows the dedicated Watch Later state for SOURCE_UNSUPPORTED, regardless of wording', async () => {
    mockApi({ 'POST /api/v1/sources': { status: 422, error: { code: 'SOURCE_UNSUPPORTED', message: 'reworded' } } });
    await renderWithProviders(<AddSourceModal visible={true} onClose={jest.fn()} />);
    await fireEvent.changeText(screen.getByPlaceholderText(/youtube.com\/playlist/), 'WL');
    await fireEvent.press(screen.getByRole('button', { name: 'Add source' }));
    expect(screen.getByText('System Playlist Restricted')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Got it, try another URL' }));
    expect(screen.getByPlaceholderText(/youtube.com\/playlist/)).toBeTruthy();
  });

  it('cancel clears state and closes', async () => {
    const onClose = jest.fn();
    useQueueStore.setState({ addSourceError: 'old', addSourceErrorCode: 'X' });
    await renderWithProviders(<AddSourceModal visible={true} onClose={onClose} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel adding content source' }));
    expect(onClose).toHaveBeenCalled();
    expect(useQueueStore.getState().addSourceError).toBeNull();
  });
});

describe('SyncProgressBar', () => {
  const base = useQueueStore.getState().syncProgress;

  it('renders nothing when idle', async () => {
    await renderWithProviders(<SyncProgressBar />);
    expect(screen.queryByText(/Sync/)).toBeNull();
  });

  it('shows determinate progress against the estimate and can cancel', async () => {
    useQueueStore.setState({ syncProgress: { ...base, isSyncing: true, itemsSyncedTotal: 250, estimatedTotal: 1000 } });
    await renderWithProviders(<SyncProgressBar />);
    expect(screen.getByText('250 of ~1000 items synced')).toBeTruthy();
    // VoiceOver reads a progressbar's value, not its label, so the count lives there.
    expect(screen.getByRole('progressbar', { name: 'Syncing content source' })).toHaveAccessibilityValue({
      min: 0,
      max: 100,
      now: 25,
      text: '250 of about 1000 items synced',
    });
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel content sync' }));
    expect(useQueueStore.getState().syncProgress.isCancelled).toBe(true);
  });

  it('shows an unknown estimate and caps at 100%', async () => {
    useQueueStore.setState({ syncProgress: { ...base, isSyncing: true, itemsSyncedTotal: 5000, estimatedTotal: null } });
    await renderWithProviders(<SyncProgressBar />);
    expect(screen.getByText('5000 of ~1,000+ items synced')).toBeTruthy();
    expect(screen.getByRole('progressbar')).toHaveAccessibilityValue({
      now: 100,
      text: '5000 of about 1,000+ items synced',
    });
  });

  it('shows the error after a failed sync', async () => {
    useQueueStore.setState({ syncProgress: { ...base, isSyncing: false, error: 'quota' } });
    await renderWithProviders(<SyncProgressBar />);
    expect(screen.getByRole('alert', { name: 'Sync error: quota' })).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });
});
