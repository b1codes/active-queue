import React from 'react';
import type { ActivityIndicatorProps } from 'react-native';
import { registerRootComponent } from 'expo';

// The module object every other module reads from (a namespace import would be Babel's
// interop copy, and patching it would change nothing).
// eslint-disable-next-line @typescript-eslint/no-require-imports
const ReactNative = require('react-native') as typeof import('react-native');

// UIKit's spinner keeps turning under Reduce Motion, so a capture of a busy button would
// land on a different frame each run. Before any story loads, swap React Native's
// ActivityIndicator for a stopped one that stays visible: its resting frame is what gets
// compared. App modules read it from react-native's exports at render time, so they get
// this one.
const Spinning = ReactNative.ActivityIndicator;
const Still = React.forwardRef<React.ComponentRef<typeof Spinning>, ActivityIndicatorProps>(
  function StillActivityIndicator(props, ref) {
    return React.createElement(Spinning, { ...props, ref, animating: false, hidesWhenStopped: false });
  },
);
Object.defineProperty(ReactNative, 'ActivityIndicator', { configurable: true, get: () => Still });

// eslint-disable-next-line @typescript-eslint/no-require-imports -- after the swap above
const { ScreenshotRoot } = require('./ScreenshotRoot') as typeof import('./ScreenshotRoot');
registerRootComponent(ScreenshotRoot);
