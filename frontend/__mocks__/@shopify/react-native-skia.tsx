// Manual Jest mock for @shopify/react-native-skia (auto-applied: adjacent to node_modules).
// Skia's own jestSetup needs a CanvasKit WASM global; component and screen tests only
// need the Tier 3 glass tree to mount, so each primitive renders as a plain host View
// tagged with its Skia name for queries/snapshots.
import React from 'react';
import { View } from 'react-native';

function primitive(name: string) {
  const Component = ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement(View, { testID: `skia-${name}`, ...props }, children);
  Component.displayName = `Skia.${name}`;
  return Component;
}

export const Canvas = primitive('Canvas');
export const RoundedRect = primitive('RoundedRect');
export const BackdropFilter = primitive('BackdropFilter');
export const Blur = primitive('Blur');
export const ColorMatrix = primitive('ColorMatrix');
export const LinearGradient = primitive('LinearGradient');
export const vec = (x: number, y: number) => ({ x, y });
