/**
 * The monkey must fail on each fault it claims to catch, and replay the same walk from
 * the same seed. Each screen here hides one fault behind a single button, so any walk
 * long enough to press it must report it.
 */
import React, { useState } from 'react';
import { ActivityIndicator, TouchableOpacity, View } from 'react-native';
import { Text } from '@/core/components/Text';
import { resetRouter, router } from '@/test-utils/router';
import { resetStores } from '@/test-utils';
import { runMonkey } from '@/test-utils/monkey';
import { apiClient } from '@/core/api/apiClient';

jest.mock('expo-router', () => require('@/test-utils/router').expoRouterMock);

beforeEach(() => {
  resetStores();
  resetRouter();
});

function Button({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <TouchableOpacity accessibilityRole="button" accessibilityLabel={label} onPress={onPress}>
      <Text>{label}</Text>
    </TouchableOpacity>
  );
}

function Faulty({ fault }: { fault: () => void | Promise<void> }) {
  const [shown, setShown] = useState('ready');
  return (
    <View>
      <Text>{shown}</Text>
      <Button label="Fault" onPress={() => void fault()} />
      <Button label="Fine" onPress={() => setShown('ready')} />
    </View>
  );
}

const noop = () => undefined;

const run = (screen: React.ComponentType, seed = 1) =>
  runMonkey({ seed, steps: 40, screens: { '/home': screen }, start: { path: '/home', params: {} } });

describe('the monkey fails on', () => {
  it('a handler that throws', async () => {
    const Throws = () => (
      <Faulty
        fault={() => {
          throw new Error('boom');
        }}
      />
    );
    await expect(run(Throws)).rejects.toThrow(/seed 1, start \/home\): action threw: Error: boom/);
  });

  it('a console.error', async () => {
    const Logs = () => <Faulty fault={() => console.error('Warning: something React dislikes')} />;
    await expect(run(Logs)).rejects.toThrow(/console\.error: Warning: something React dislikes/);
  });

  it('rendered "undefined"', async () => {
    function Screen() {
      const [label, setLabel] = useState('3 min');
      return (
        <View>
          <Text>{label}</Text>
          <Button label="Fault" onPress={() => setLabel(`${String(undefined)} min`)} />
        </View>
      );
    }
    await expect(run(Screen)).rejects.toThrow(/rendered "undefined"/);
  });

  it('a request to a route the API does not have', async () => {
    const CallsNothing = () => <Faulty fault={() => apiClient('/api/v1/nope').then(noop, noop)} />;
    await expect(run(CallsNothing)).rejects.toThrow(/routes the API doesn't have: GET \/api\/v1\/nope/);
  });

  it('a screen that leaves the user stuck', async () => {
    function Stuck() {
      const [stuck, setStuck] = useState(false);
      if (stuck) return <ActivityIndicator accessibilityLabel="Loading forever" />;
      return <Button label="Go" onPress={() => setStuck(true)} />;
    }
    await expect(run(Stuck)).rejects.toThrow(/unrecoverable screen at \/home/);
  });

  it('navigation to a route that does not exist', async () => {
    const Navigates = () => <Faulty fault={() => router.push('/nowhere')} />;
    await expect(run(Navigates)).rejects.toThrow(/navigated to unknown route \/nowhere/);
  });
});

it('replays the same walk from the same seed', async () => {
  const walk = async (seed: number) => {
    const presses: string[] = [];
    function Recorder() {
      return (
        <View>
          {['a', 'b', 'c', 'd'].map((k) => (
            <Button key={k} label={k} onPress={() => presses.push(k)} />
          ))}
        </View>
      );
    }
    await runMonkey({ seed, steps: 30, screens: { '/r': Recorder }, start: { path: '/r', params: {} } });
    return presses.join('');
  };
  const first = await walk(42);
  expect(first.length).toBeGreaterThan(10);
  expect(await walk(42)).toBe(first);
  expect(await walk(43)).not.toBe(first);
});
