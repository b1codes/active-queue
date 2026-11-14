import React, { useEffect, useMemo } from 'react';
import { Image, Settings, StyleSheet, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Text } from '@/core/components/Text';
import { overrideGlassTier } from '@/core/hooks/useGlassTier';
import { colors } from '@/core/theme';
import preview from '../preview';
import { collectStories, decorate, parseHarnessArgs, type StoryDecorator, type StoryModule } from './catalog';

// Metro's require.context: every story under src/, the same set .rnstorybook/main.ts loads.
const storyContext = require.context('../../src', true, /\.stories\.tsx$/);
const THUMBNAIL_URI = Image.resolveAssetSource(require('./thumbnail.png')).uri;
const catalog = collectStories(
  storyContext.keys().map((key) => storyContext(key) as StoryModule),
  THUMBNAIL_URI,
);
const byId = new Map(catalog.map((entry) => [entry.id, entry]));

/** The capture script waits for no pixel to change, so this only has to be distinctive. */
function HarnessMessage({ text, testID }: { text: string; testID: string }) {
  return (
    <View style={[styles.fill, styles.message]} testID={testID}>
      <Text style={styles.messageText}>{text}</Text>
    </View>
  );
}

/**
 * Visual-regression harness (ClickUp 86bcxruz4). Built only by
 * `scripts/ios-sim-build.sh screenshots`, which bundles this file as the entry instead
 * of expo-router. It renders one story full screen, chosen by launch arguments:
 *
 *   xcrun simctl launch --terminate-running-process <udid> com.b1codes.activequeue \
 *     -vrStory core-glassheader--with-subtitle -vrTier 3
 *
 * (Not a deep link: iOS 26 asks "Open in ActiveQueue?" before handing one over.)
 * scripts/screenshots/capture.js drives it. The story renders inside preview.tsx's
 * decorators, on the chosen glass tier, with the clock frozen (index.tsx) and remote
 * images replaced by a bundled thumbnail.
 */
export function ScreenshotRoot() {
  // Read once: each capture is a fresh launch.
  const [story, tier, nonce] = [Settings.get('vrStory'), Settings.get('vrTier'), Settings.get('vrNonce')];
  const target = story == null ? null : (parseHarnessArgs(story, tier) ?? 'invalid');

  const entry = target && target !== 'invalid' ? byId.get(target.storyId) : undefined;
  const rendered = useMemo(() => {
    if (!entry || !target || target === 'invalid') return null;
    // Before the story mounts, so every surface in it resolves to the requested tier.
    overrideGlassTier(target.tier);
    const Story = decorate(entry.Component, (preview.decorators ?? []) as StoryDecorator[]);
    return <Story />;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- launch arguments never change
  }, []);

  // Tells capture.js this launch has mounted its screen, so it never mistakes the home
  // screen or the splash (both hold still while a cold launch is slow) for a story. The
  // script listens on localhost, which the simulator shares with the Mac.
  const readyUrl = Settings.get('vrReadyUrl');
  useEffect(() => {
    if (nonce == null || typeof readyUrl !== 'string') return;
    const timer = setTimeout(() => {
      fetch(`${readyUrl}?nonce=${encodeURIComponent(String(nonce))}`).catch(() => {
        // The script times out and reports the story; nothing to do here.
      });
    }, 50);
    return () => clearTimeout(timer);
  }, [nonce, readyUrl]);

  let body: React.ReactElement;
  if (target === null) body = <HarnessMessage testID="vr-idle" text={`${catalog.length} stories`} />;
  else if (target === 'invalid') body = <HarnessMessage testID="vr-invalid" text="VR: bad arguments" />;
  else if (!rendered) body = <HarnessMessage testID="vr-unknown" text={`VR: unknown ${target.storyId}`} />;
  else body = rendered;

  return (
    <View style={styles.fill}>
      <StatusBar hidden />
      {body}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.void },
  // Magenta: unlike any app color, so a capture of this screen can't pass for a story.
  message: { alignItems: 'center', justifyContent: 'center', backgroundColor: '#FF00FF' },
  messageText: { color: '#000000', fontSize: 20 },
});
