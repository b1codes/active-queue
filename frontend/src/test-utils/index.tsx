/**
 * Shared helpers for component and screen tests.
 *
 * - `renderWithProviders` mounts under the real Redux store (the stores are module
 *   singletons) plus SafeArea metrics, so components behave as they do in the app.
 * - `resetStores` puts every slice back to initial state between tests.
 * - `mockApi` replaces global fetch with a route table that speaks the API envelope,
 *   records every call, and reports unmatched requests loudly.
 */
import React from 'react';
import { render, type RenderOptions } from '@testing-library/react-native';
import { Provider } from 'react-redux';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { resetUserScopedState, store } from '@/store';
import { setAuthState } from '@/features/auth/authSlice';

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

export function renderWithProviders(ui: React.ReactElement, options?: RenderOptions) {
  return render(
    <Provider store={store}>
      <SafeAreaProvider initialMetrics={metrics}>{ui}</SafeAreaProvider>
    </Provider>,
    options
  );
}

export function resetStores(auth: Partial<Parameters<typeof setAuthState>[0]> = {}): void {
  store.dispatch(resetUserScopedState());
  store.dispatch(
    setAuthState({
      user: null,
      idToken: 'test-token',
      isAuthenticated: true,
      isLoading: false,
      error: null,
      ...auth,
    })
  );
}

export interface MockResponse {
  status?: number;
  data?: unknown;
  error?: { code: string; message: string; details?: { field: string; issue: string }[] };
  headers?: Record<string, string>;
}

type Handler = MockResponse | ((req: { url: string; body: unknown }) => MockResponse);

export interface ApiCall {
  method: string;
  path: string;
  query: Record<string, string>;
  body: unknown;
  headers: Record<string, string>;
}

/**
 * Route keys are "METHOD /path" (no query string). A handler may be a fixed response,
 * a function of the request, or an array consumed one response per call.
 */
export function mockApi(routes: Record<string, Handler | Handler[]>) {
  const calls: ApiCall[] = [];
  const queues = new Map<string, Handler[]>();
  for (const [key, h] of Object.entries(routes)) {
    queues.set(key, Array.isArray(h) ? [...h] : [h]);
  }

  const fetchMock = jest.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    const method = (init.method ?? 'GET').toUpperCase();
    // Match on the decoded path, as the server's router does (fx%3Aid == fx:id).
    const pathname = decodeURIComponent(url.pathname);
    const key = `${method} ${pathname}`;
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({
      method,
      path: pathname,
      query: Object.fromEntries(url.searchParams.entries()),
      body,
      headers: (init.headers ?? {}) as Record<string, string>,
    });

    const queue = queues.get(key);
    if (!queue || queue.length === 0) {
      throw new Error(`mockApi: unexpected request ${key}`);
    }
    const handler = queue.length > 1 ? queue.shift()! : queue[0];
    const res = typeof handler === 'function' ? handler({ url: input, body }) : handler;
    const status = res.status ?? (res.error ? 400 : 200);
    const envelope = res.error
      ? { status: 'error', data: null, error: { details: [], ...res.error } }
      : { status: 'success', data: res.data ?? null, error: null };
    const headers = new Map(Object.entries(res.headers ?? {}));
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: { get: (name: string) => headers.get(name) ?? null },
      json: async () => envelope,
    } as unknown as Response;
  });

  global.fetch = fetchMock as unknown as typeof fetch;
  return {
    calls,
    fetchMock,
    callsTo: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path),
  };
}

/** Make every fetch reject the way RN does when offline. */
export function mockNetworkDown(): void {
  global.fetch = jest.fn(async () => {
    throw new TypeError('Network request failed');
  }) as unknown as typeof fetch;
}

export * from './fixtures';
