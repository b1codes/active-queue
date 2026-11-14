import React from 'react';
import { act, render, waitFor } from '@testing-library/react-native';
import * as firebaseAuth from 'firebase/auth';
import { registeredScreens, resetRouter, router } from '@/test-utils/router';
import { renderWithProviders, resetStores } from '@/test-utils';
import RootLayout from '@app/_layout';
import AppLayout from '@app/(app)/_layout';
import AuthLayout from '@app/(auth)/_layout';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);
// The real provider renders nothing until native reports insets, which never happens here.
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const onIdTokenChanged = firebaseAuth.onIdTokenChanged as jest.Mock;

beforeEach(() => {
  resetRouter();
  onIdTokenChanged.mockImplementation(() => () => undefined);
});

describe('root layout auth guard', () => {
  it('shows only the loading pulse while auth resolves, and subscribes to token changes', async () => {
    resetStores({ isLoading: true, isAuthenticated: false });
    await render(<RootLayout />);
    expect(onIdTokenChanged).toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  // Stack.Protected registers only the group the user may be in: expo-router then sends
  // a signed-out launch straight to sign-in without ever mounting the queue (which used to
  // fetch with no token first), and moves between groups when auth changes.
  it('offers a signed-out user only the auth screens', async () => {
    onIdTokenChanged.mockImplementation((_a: unknown, cb: (u: null) => void) => {
      cb(null);
      return () => undefined;
    });
    resetStores({ isAuthenticated: false, user: null });
    await render(<RootLayout />);
    await waitFor(() => expect(registeredScreens).toEqual(['(auth)']));
    expect(router.replace).not.toHaveBeenCalled();
  });

  it('offers a signed-in user only the app', async () => {
    const user = { uid: 'u1', getIdToken: jest.fn().mockResolvedValue('t') };
    onIdTokenChanged.mockImplementation((_a: unknown, cb: (u: unknown) => Promise<void>) => {
      void cb(user);
      return () => undefined;
    });
    resetStores({ isAuthenticated: true, user: user as never });
    await render(<RootLayout />);
    await waitFor(() => expect(registeredScreens).toEqual(['(app)']));
  });

  it('switches groups when the user signs out', async () => {
    let emit: (u: unknown) => Promise<void> = async () => undefined;
    const user = { uid: 'u1', getIdToken: jest.fn().mockResolvedValue('t') };
    onIdTokenChanged.mockImplementation((_a: unknown, cb: (u: unknown) => Promise<void>) => {
      emit = cb;
      void cb(user);
      return () => undefined;
    });
    resetStores({ isAuthenticated: true, user: user as never });
    await render(<RootLayout />);
    await waitFor(() => expect(registeredScreens).toEqual(['(app)']));
    await act(async () => {
      await emit(null);
    });
    await waitFor(() => expect(registeredScreens).toEqual(['(auth)']));
  });

  it('unsubscribes from token changes on unmount', async () => {
    const unsubscribe = jest.fn();
    onIdTokenChanged.mockImplementation(() => unsubscribe);
    resetStores();
    const { unmount } = await render(<RootLayout />);
    await unmount();
    expect(unsubscribe).toHaveBeenCalled();
  });
});

describe('group layouts', () => {
  it('render their navigators', async () => {
    await expect(renderWithProviders(<AppLayout />)).resolves.toBeTruthy();
    await expect(render(<AuthLayout />)).resolves.toBeTruthy();
  });
});
