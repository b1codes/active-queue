import React from 'react';
import { act, fireEvent, screen } from '@testing-library/react-native';
import { refocus, resetRouter, router } from '@/test-utils/router';
import { mockApi, renderWithProviders, resetStores, session } from '@/test-utils';
import HistoryScreen from '@app/(app)/history';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

beforeEach(() => {
  resetStores();
  resetRouter();
});

describe('HistoryScreen', () => {
  it('lists sessions with honest status labels and pages with the cursor', async () => {
    const api = mockApi({
      'GET /api/v1/sessions': [
        {
          data: {
            items: [
              session({ id: 'a', status: 'completed' }),
              session({ id: 'b', status: 'abandoned', match_mode: 'time_first' }),
            ],
            next_cursor: 'c1',
          },
        },
        { data: { items: [session({ id: 'c', status: 'in_progress' })], next_cursor: null } },
      ],
    });
    await renderWithProviders(<HistoryScreen />);
    expect(await screen.findByText('Completed')).toBeTruthy();
    expect(screen.getByText('Abandoned')).toBeTruthy();
    expect(screen.queryByText(/Verified/)).toBeNull();

    await fireEvent(screen.getByTestId('history-list'), 'endReached');
    expect(await screen.findByText('In progress')).toBeTruthy();
    expect(api.calls[1].query.cursor).toBe('c1');
  });

  it('a refresh on refocus wins over a next-page request still in flight', async () => {
    const api = mockApi({
      'GET /api/v1/sessions': [
        { data: { items: [session({ id: 'a', status: 'completed' })], next_cursor: 'c1' } },
        { data: { items: [session({ id: 'stale', status: 'abandoned' })], next_cursor: 'c2' } },
        { data: { items: [session({ id: 'a', status: 'completed' })], next_cursor: 'c1-fresh' } },
        { data: { items: [session({ id: 'd', status: 'pending' })], next_cursor: null } },
      ],
    });
    // Hold the page-2 response until after the refresh has answered.
    const mocked = api.fetchMock.getMockImplementation()!;
    let releasePage2!: () => void;
    const page2Held = new Promise<void>((resolve) => (releasePage2 = resolve));
    api.fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      const res = await mocked(input, init);
      if (new URL(input).searchParams.get('cursor') === 'c1') await page2Held;
      return res;
    });

    await renderWithProviders(<HistoryScreen />);
    expect(await screen.findByText('Completed')).toBeTruthy();
    await fireEvent(screen.getByTestId('history-list'), 'endReached'); // page 2 in flight
    await act(async () => refocus());
    await act(async () => releasePage2());

    expect(screen.getAllByText('Completed')).toHaveLength(1);
    expect(screen.queryByText('Abandoned')).toBeNull();
    // The cursor is the refresh's, so the next page continues from fresh data.
    await fireEvent(screen.getByTestId('history-list'), 'endReached');
    expect(await screen.findByText('Not started')).toBeTruthy();
    expect(api.calls.at(-1)?.query.cursor).toBe('c1-fresh');
  });

  it('shows the empty state with a way to start', async () => {
    mockApi({ 'GET /api/v1/sessions': { data: { items: [], next_cursor: null } } });
    await renderWithProviders(<HistoryScreen />);
    expect(await screen.findByText('No Sessions Yet')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Start a Time Block Session' }));
    expect(router.push).toHaveBeenCalledWith('/(app)/blocks');
  });

  it('shows a retryable error', async () => {
    mockApi({
      'GET /api/v1/sessions': [
        { status: 503, error: { code: 'X', message: 'down' } },
        { data: { items: [session({ status: 'pending' })], next_cursor: null } },
      ],
    });
    await renderWithProviders(<HistoryScreen />);
    expect(await screen.findByText("Couldn't load history")).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Retry loading history' }));
    expect(await screen.findByText('Not started')).toBeTruthy();
  });
});
