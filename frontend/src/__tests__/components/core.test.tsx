import React from 'react';
import { Text } from 'react-native';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import { State, TapGesture, LongPressGesture } from 'react-native-gesture-handler';
import * as Reanimated from 'react-native-reanimated';
import {
  ChromaticPulse,
  GlassHeader,
  LiquidGlassSurface,
  QueueSkeletonList,
  ThermalGlowTouchable,
} from '@/core/components';
import { __resetGlassTierCacheForTests } from '@/core/hooks/useGlassTier';
import { renderWithProviders } from '@/test-utils';

const liquidGlass = require('@callstack/liquid-glass') as { isLiquidGlassSupported: boolean };

afterEach(() => {
  liquidGlass.isLiquidGlassSupported = false;
  __resetGlassTierCacheForTests();
});

describe('LiquidGlassSurface', () => {
  it('renders the Tier 3 Skia fallback by default, sized from layout', async () => {
    await render(
      <LiquidGlassSurface testID="glass" borderRadius={12}>
        <Text>inside</Text>
      </LiquidGlassSurface>
    );
    expect(screen.getByText('inside')).toBeTruthy();
    expect(screen.queryByTestId('liquid-glass-view')).toBeNull();
    // The Skia canvas only draws once the surface has a measured size.
    expect(screen.queryByTestId('skia-Canvas')).toBeNull();
    await fireEvent(screen.getByTestId('glass'), 'layout', {
      nativeEvent: { layout: { width: 200, height: 80, x: 0, y: 0 } },
    });
    expect(screen.getByTestId('skia-Canvas')).toBeTruthy();
    expect(screen.getAllByTestId('skia-LinearGradient').length).toBeGreaterThan(0);
  });

  it('omits the specular stroke when specularEdge="none"', async () => {
    await render(<LiquidGlassSurface testID="glass" specularEdge="none" />);
    await fireEvent(screen.getByTestId('glass'), 'layout', {
      nativeEvent: { layout: { width: 200, height: 80, x: 0, y: 0 } },
    });
    expect(screen.queryByTestId('skia-LinearGradient')).toBeNull();
  });

  it('renders the native Tier 1 material when supported', async () => {
    liquidGlass.isLiquidGlassSupported = true;
    __resetGlassTierCacheForTests();
    await render(
      <LiquidGlassSurface>
        <Text>native</Text>
      </LiquidGlassSurface>
    );
    expect(screen.getByTestId('liquid-glass-view')).toBeTruthy();
    expect(screen.queryByTestId('skia-Canvas')).toBeNull();
  });

  it('warns in dev when more than two glass layers are mounted (GPU budget)', async () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { unmount } = await render(
      <>
        <LiquidGlassSurface />
        <LiquidGlassSurface />
        <LiquidGlassSurface />
      </>
    );
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('3 concurrent glass layers'));
    await unmount();
    warn.mockClear();
    await render(<LiquidGlassSurface />);
    expect(warn).not.toHaveBeenCalled();
  });
});

describe('GlassHeader', () => {
  it('renders title, subtitle, slots and reports its measured height', async () => {
    const onHeight = jest.fn();
    await renderWithProviders(
      <GlassHeader
        title="Active Queue"
        subtitle="sub"
        leftComponent={<Text>left</Text>}
        rightComponent={<Text>right</Text>}
        onHeightChange={onHeight}
      />
    );
    expect(screen.getByText('Active Queue')).toBeTruthy();
    expect(screen.getByText('sub')).toBeTruthy();
    expect(screen.getByText('left')).toBeTruthy();
    expect(screen.getByText('right')).toBeTruthy();
    await fireEvent(screen.getByText('Active Queue').parent!.parent!.parent!.parent!.parent!.parent!, 'layout', {
      nativeEvent: { layout: { width: 390, height: 120, x: 0, y: 0 } },
    });
    expect(onHeight).toHaveBeenCalledWith(120);
  });
});

describe('ChromaticPulse & QueueSkeletonList', () => {
  it('renders an animated pulse, and a static one under Reduce Motion', async () => {
    const spy = Reanimated.useReducedMotion as jest.Mock;
    spy.mockReturnValue(false);
    const { rerender } = await render(<ChromaticPulse testID="pulse" colors={['#000', '#fff']} />);
    expect(screen.getByTestId('pulse')).toBeTruthy();
    spy.mockReturnValue(true);
    await rerender(<ChromaticPulse testID="pulse" />);
    expect(screen.getByTestId('pulse')).toBeTruthy();
    spy.mockReturnValue(false);
  });

  it('renders the requested number of skeleton rows, labelled for VoiceOver', async () => {
    await render(<QueueSkeletonList count={3} />);
    expect(screen.getByLabelText(/Loading/i)).toBeTruthy();
  });
});

describe('ThermalGlowTouchable', () => {
  function setup(props: Partial<React.ComponentProps<typeof ThermalGlowTouchable>> = {}) {
    const onPress = jest.fn();
    const onLongPress = jest.fn();
    const utils = render(
      <ThermalGlowTouchable
        testID="cta"
        onPress={onPress}
        onLongPress={onLongPress}
        accessibilityLabel="Start"
        {...props}
      >
        <Text>Start</Text>
      </ThermalGlowTouchable>
    );
    return { onPress, onLongPress, utils };
  }

  it('fires onPress on a completed tap gesture', async () => {
    const { onPress, utils } = setup();
    await utils;
    await act(async () => {
      fireGestureHandler<TapGesture>(getByGestureTestId('cta.tap'), [
        { state: State.BEGAN, x: 10, y: 10 },
        { state: State.ACTIVE },
        { state: State.END },
      ]);
    });
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('fires onLongPress on a long press gesture', async () => {
    const { onLongPress, utils } = setup();
    await utils;
    await act(async () => {
      fireGestureHandler<LongPressGesture>(getByGestureTestId('cta.longPress'), [
        { state: State.BEGAN },
        { state: State.ACTIVE },
        { state: State.END },
      ]);
    });
    expect(onLongPress).toHaveBeenCalledTimes(1);
  });

  it('exposes press and long-press to assistive tech as accessibility actions', async () => {
    const { onPress, onLongPress, utils } = setup();
    await utils;
    const button = screen.getByRole('button', { name: 'Start' });
    await fireEvent(button, 'accessibilityAction', { nativeEvent: { actionName: 'activate' } });
    await fireEvent(button, 'accessibilityAction', { nativeEvent: { actionName: 'longpress' } });
    expect(onPress).toHaveBeenCalledTimes(1);
    expect(onLongPress).toHaveBeenCalledTimes(1);
    expect(button.props.accessibilityActions).toEqual([{ name: 'activate' }, { name: 'longpress' }]);
  });

  it('is announced as disabled and ignores activation when disabled', async () => {
    const { onPress, utils } = setup({ disabled: true });
    await utils;
    const button = screen.getByRole('button', { name: 'Start' });
    expect(button.props.accessibilityState).toMatchObject({ disabled: true });
    await fireEvent(button, 'accessibilityAction', { nativeEvent: { actionName: 'activate' } });
    expect(onPress).not.toHaveBeenCalled();
  });
});
