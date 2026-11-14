// Manual Jest mock for @callstack/liquid-glass (auto-applied: adjacent to node_modules).
// Tests run as "not iOS 26", i.e. Tier 3. A suite that needs Tier 1 sets
// `require('@callstack/liquid-glass').isLiquidGlassSupported = true` and resets the
// useGlassTier cache (see core.test.tsx).
import React from 'react';
import { View } from 'react-native';

module.exports = {
  isLiquidGlassSupported: false,
  LiquidGlassView: ({ children, testID, ...props }: { children?: React.ReactNode; testID?: string }) =>
    React.createElement(View, { ...props, testID: testID ?? 'liquid-glass-view' }, children),
};
