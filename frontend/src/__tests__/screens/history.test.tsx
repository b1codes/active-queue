import React from 'react';
import { fireEvent, screen } from '@testing-library/react-native';
import { resetRouter, router } from '@/test-utils/router';
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
