import React from 'react';
import { Alert } from 'react-native';
import { fireEvent, screen } from '@testing-library/react-native';
import * as firebaseAuth from 'firebase/auth';
import { renderWithProviders, resetStores } from '@/test-utils';
import { useAuthStore } from '@/features/auth/authStore';
import SignInScreen from '@app/(auth)/sign-in';
import SettingsScreen from '@app/(app)/settings';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

const g = globalThis as { __DEV__?: boolean };
const originalDev = g.__DEV__;
afterEach(() => {
  g.__DEV__ = originalDev;
  delete process.env.EXPO_PUBLIC_USE_EMULATOR;
});

describe('SignInScreen', () => {
  beforeEach(() => resetStores({ isAuthenticated: false, user: null }));

  it('requires both fields, then signs in with email + password', async () => {
    (firebaseAuth.signInWithEmailAndPassword as jest.Mock).mockResolvedValue({});
    await renderWithProviders(<SignInScreen />);
    const signIn = screen.getByRole('button', { name: 'Sign in' });
    expect(signIn.props.accessibilityState).toMatchObject({ disabled: true });

    await fireEvent.changeText(screen.getByLabelText('Email address'), 'a@b.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'pw123456');
    await fireEvent(screen.getByRole('button', { name: 'Sign in' }), 'accessibilityAction', {
      nativeEvent: { actionName: 'activate' },
    });
    expect(firebaseAuth.signInWithEmailAndPassword).toHaveBeenCalledWith(expect.anything(), 'a@b.com', 'pw123456');
  });

  it('turns Firebase credential errors into a plain-language alert', async () => {
    resetStores({ isAuthenticated: false, error: 'Firebase: Error (auth/invalid-credential).' });
    await renderWithProviders(<SignInScreen />);
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('Invalid email address or password. Please verify your details.')).toBeTruthy();
  });

  it('passes other errors through and survives a failed sign-in', async () => {
    (firebaseAuth.signInWithEmailAndPassword as jest.Mock).mockRejectedValue(new Error('network down'));
    await renderWithProviders(<SignInScreen />);
    await fireEvent.changeText(screen.getByLabelText('Email address'), 'a@b.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'pw');
    await fireEvent(screen.getByRole('button', { name: 'Sign in' }), 'accessibilityAction', {
      nativeEvent: { actionName: 'activate' },
    });
    expect(await screen.findByText('network down')).toBeTruthy();
  });

  it('shows the emulator shortcut in dev builds only', async () => {
    g.__DEV__ = true;
    const { unmount } = await renderWithProviders(<SignInScreen />);
    expect(screen.getByRole('button', { name: 'Quick sign in as emulator user' })).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Quick sign in as emulator user' }));
    expect(firebaseAuth.signInWithEmailAndPassword).toHaveBeenCalled();
    await unmount();

    g.__DEV__ = false;
    await renderWithProviders(<SignInScreen />);
    expect(screen.queryByRole('button', { name: 'Quick sign in as emulator user' })).toBeNull();
  });

  it('EXPO_PUBLIC_USE_EMULATOR enables the shortcut in a release build', async () => {
    g.__DEV__ = false;
    process.env.EXPO_PUBLIC_USE_EMULATOR = 'true';
    await renderWithProviders(<SignInScreen />);
    expect(screen.getByRole('button', { name: 'Quick sign in as emulator user' })).toBeTruthy();
  });
});

describe('SettingsScreen', () => {
  it('shows the account and signs out', async () => {
    resetStores({ user: { uid: 'u-123', email: 'me@x.com' } as never });
    await renderWithProviders(<SettingsScreen />);
    expect(screen.getByText('u-123')).toBeTruthy();
    expect(screen.getByText('me@x.com')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Sign out' }));
    expect(firebaseAuth.signOut).toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('falls back when signed out, and hides dev tools in release builds', async () => {
    g.__DEV__ = false;
    resetStores({ user: null });
    await renderWithProviders(<SettingsScreen />);
    expect(screen.getByText('Not signed in')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Re-authenticate as Emulator User' })).toBeNull();
  });

  it('dev re-auth reports success', async () => {
    g.__DEV__ = true;
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    (firebaseAuth.signInWithEmailAndPassword as jest.Mock).mockResolvedValue({});
    resetStores();
    await renderWithProviders(<SettingsScreen />);
    await fireEvent.press(screen.getByRole('button', { name: 'Re-authenticate as Emulator User' }));
    expect(alert).toHaveBeenCalledWith('Success', expect.any(String));
  });

  it('reports a failed sign-out', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    (firebaseAuth.signOut as jest.Mock).mockRejectedValueOnce(new Error('x'));
    resetStores();
    await renderWithProviders(<SettingsScreen />);
    await fireEvent.press(screen.getByRole('button', { name: 'Sign out' }));
    // signOut records the error in the store rather than throwing.
    expect(useAuthStore.getState().error).toBe('x');
    expect(alert).not.toHaveBeenCalled();
  });
});
