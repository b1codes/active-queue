/**
 * expo-router test double. Import it in a test via
 *   jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);
 * then drive params with `setParams` and assert navigation through `router`.
 */
import React, { useEffect } from 'react';

export const router = {
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
};

let params: Record<string, string> = {};
let segments: string[] = ['(app)'];

export function setParams(next: Record<string, string>): void {
  params = next;
}

export function setSegments(next: string[]): void {
  segments = next;
}

export function resetRouter(): void {
  router.push.mockReset();
  router.replace.mockReset();
  router.back.mockReset();
  params = {};
  segments = ['(app)'];
}

function Navigator({ children }: { children?: React.ReactNode }) {
  return React.createElement(React.Fragment, null, children);
}
type IconFn = (p: { color: string; focused: boolean; size: number }) => React.ReactNode;
Navigator.Screen = function Screen({ options }: { options?: { tabBarIcon?: IconFn } }) {
  // Render tab icons in both states so tab configuration is exercised.
  if (!options?.tabBarIcon) return null;
  return React.createElement(
    React.Fragment,
    null,
    options.tabBarIcon({ color: '#fff', focused: true, size: 22 }),
    options.tabBarIcon({ color: '#888', focused: false, size: 22 })
  );
};

export const expoRouterMock = {
  useRouter: () => router,
  useLocalSearchParams: () => params,
  useSegments: () => segments,
  // Screens refetch on focus; in tests "focus" is mount.
  useFocusEffect: (effect: () => void | (() => void)) => {
    useEffect(effect, [effect]);
  },
  Stack: Navigator,
  Tabs: Navigator,
};
