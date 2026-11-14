import * as firebaseAuth from 'firebase/auth';
import { store } from '@/store';
import { initAuth, signInWithEmulator, signOut, useAuthStore } from '@/features/auth/authStore';
import { useQueueStore } from '@/features/queue/queueStore';
import { useSessionStore } from '@/features/sessions/sessionStore';
import { feedItem, resetStores, session } from '@/test-utils';

const onIdTokenChanged = firebaseAuth.onIdTokenChanged as jest.Mock;
type Listener = (user: unknown) => Promise<void>;

function fakeUser(uid: string) {
  return { uid, getIdToken: jest.fn().mockResolvedValue(`token-${uid}`) };
}

let listener: Listener;
beforeEach(() => {
  resetStores({ user: null, isAuthenticated: false });
  onIdTokenChanged.mockImplementation((_auth: unknown, cb: Listener) => {
    listener = cb;
    return () => undefined;
  });
});

describe('account switches never leak user-scoped state (multi-account)', () => {
  it('a different uid resets the queue and the active session', async () => {
    initAuth();
    await listener(fakeUser('alice'));
    useQueueStore.setState({ feedItems: [feedItem(1)], totalUnconsumed: 1 });
    useSessionStore.setState({ currentSession: session({ user_id: 'alice' }) });

    await listener(fakeUser('bob'));
    expect(store.getState().queue.feedItems).toEqual([]);
    expect(store.getState().session.currentSession).toBeNull();
    expect(useAuthStore.getState().idToken).toBe('token-bob');
  });

  it('a token refresh for the same uid keeps state', async () => {
    initAuth();
    await listener(fakeUser('alice'));
    useQueueStore.setState({ feedItems: [feedItem(1)] });
    await listener(fakeUser('alice'));
    expect(store.getState().queue.feedItems).toHaveLength(1);
  });

  it('sign-out clears user-scoped state', async () => {
    useQueueStore.setState({ feedItems: [feedItem(1)] });
    useSessionStore.setState({ currentSession: session() });
    await signOut();
    expect(store.getState().queue.feedItems).toEqual([]);
    expect(store.getState().session.currentSession).toBeNull();
    expect(useAuthStore.getState()).toMatchObject({ isAuthenticated: false, idToken: null });
  });

  it('a failed token fetch signs the app out with an error', async () => {
    initAuth();
    await listener({ uid: 'x', getIdToken: jest.fn().mockRejectedValue(new Error('revoked')) });
    expect(useAuthStore.getState()).toMatchObject({ isAuthenticated: false, error: 'revoked' });
  });
});

describe('emulator sign-in is dev-only', () => {
  const g = globalThis as { __DEV__?: boolean };
  const original = g.__DEV__;
  afterEach(() => {
    g.__DEV__ = original;
  });

  it('refuses outside dev builds and never creates the shared test account', async () => {
    g.__DEV__ = false;
    await signInWithEmulator();
    expect(firebaseAuth.createUserWithEmailAndPassword).not.toHaveBeenCalled();
    expect(firebaseAuth.signInWithEmailAndPassword).not.toHaveBeenCalled();
    expect(useAuthStore.getState().error).toMatch(/development/);
  });

  it('in dev, signs in and falls back to creating the emulator user', async () => {
    g.__DEV__ = true;
    (firebaseAuth.signInWithEmailAndPassword as jest.Mock).mockRejectedValueOnce(new Error('no user'));
    (firebaseAuth.createUserWithEmailAndPassword as jest.Mock).mockResolvedValueOnce({});
    await signInWithEmulator();
    expect(firebaseAuth.createUserWithEmailAndPassword).toHaveBeenCalledWith(
      expect.anything(),
      'test@activequeue.dev',
      'password123'
    );
  });
});

describe('email sign-in / sign-up', () => {
  it('records sign-in failures and rethrows', async () => {
    const { signInWithEmail, signUpWithEmail } = jest.requireActual('@/features/auth/authStore');
    (firebaseAuth.signInWithEmailAndPassword as jest.Mock).mockRejectedValueOnce(new Error('bad pw'));
    await expect(signInWithEmail('a@b.com', 'x')).rejects.toThrow('bad pw');
    expect(useAuthStore.getState()).toMatchObject({ isLoading: false, error: 'bad pw' });

    (firebaseAuth.createUserWithEmailAndPassword as jest.Mock).mockResolvedValueOnce({});
    await signUpWithEmail('new@b.com', 'secret12');
    expect(firebaseAuth.createUserWithEmailAndPassword).toHaveBeenCalledWith(expect.anything(), 'new@b.com', 'secret12');

    (firebaseAuth.createUserWithEmailAndPassword as jest.Mock).mockRejectedValueOnce(new Error('taken'));
    await expect(signUpWithEmail('new@b.com', 'secret12')).rejects.toThrow('taken');
    expect(useAuthStore.getState().error).toBe('taken');
  });

  it('dev emulator sign-in reports when both sign-in and create fail', async () => {
    const g = globalThis as { __DEV__?: boolean };
    g.__DEV__ = true;
    (firebaseAuth.signInWithEmailAndPassword as jest.Mock).mockRejectedValueOnce(new Error('no'));
    (firebaseAuth.createUserWithEmailAndPassword as jest.Mock).mockRejectedValueOnce(new Error('emulator down'));
    await signInWithEmulator();
    expect(useAuthStore.getState()).toMatchObject({ isLoading: false, error: 'emulator down' });
  });

  it('selector form of the hook-free getters exposes actions', () => {
    expect(typeof useAuthStore.getState().signOut).toBe('function');
    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });
});
