import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import * as firebaseAuth from 'firebase/auth';
import { resetRouter, router, setSegments } from '@/test-utils/router';
import { renderWithProviders, resetStores } from '@/test-utils';
import RootLayout from '@app/_layout';
import AppLayout from '@app/(app)/_layout';
import AuthLayout from '@app/(auth)/_layout';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

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

  it('sends a signed-out user inside the app to sign-in', async () => {
    // initAuth flips isLoading back on; resolve it as "no user" from the listener.
    onIdTokenChanged.mockImplementation((_a: unknown, cb: (u: null) => void) => {
      cb(null);
      return () => undefined;
    });
    resetStores({ isAuthenticated: false, user: null });
    setSegments(['(app)']);
    await render(<RootLayout />);
    expect(router.replace).toHaveBeenCalledWith('/(auth)/sign-in');
  });

  it('sends a signed-in user on the auth screens into the app', async () => {
    const user = { uid: 'u1', getIdToken: jest.fn().mockResolvedValue('t') };
    onIdTokenChanged.mockImplementation((_a: unknown, cb: (u: unknown) => Promise<void>) => {
      void cb(user);
      return () => undefined;
    });
    resetStores({ isAuthenticated: true, user: user as never });
    setSegments(['(auth)']);
    await render(<RootLayout />);
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/(app)'));
  });

  it('leaves a signed-in user inside the app alone', async () => {
    const user = { uid: 'u1', getIdToken: jest.fn().mockResolvedValue('t') };
    onIdTokenChanged.mockImplementation((_a: unknown, cb: (u: unknown) => Promise<void>) => {
      void cb(user);
      return () => undefined;
    });
    resetStores({ isAuthenticated: true, user: user as never });
    setSegments(['(app)']);
    await render(<RootLayout />);
    expect(router.replace).not.toHaveBeenCalled();
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
