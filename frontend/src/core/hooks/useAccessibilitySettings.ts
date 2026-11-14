import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

type Setting = 'reduceMotion' | 'reduceTransparency';

const query: Record<Setting, () => Promise<boolean>> = {
  reduceMotion: () => AccessibilityInfo.isReduceMotionEnabled(),
  reduceTransparency: () => AccessibilityInfo.isReduceTransparencyEnabled(),
};

/**
 * Follows an iOS accessibility setting live: the initial value is read on mount and every
 * change is applied as it happens, so toggling it in Settings takes effect without a relaunch.
 * Reads false until the first answer arrives.
 */
function useAccessibilitySetting(setting: Setting): boolean {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let mounted = true;
    query[setting]()
      .then((value) => {
        if (mounted) setEnabled(value);
      })
      .catch(() => {
        // Unsupported on this platform: keep the default.
      });
    const sub = AccessibilityInfo.addEventListener(`${setting}Changed`, (value: boolean) => {
      if (mounted) setEnabled(value);
    });
    return () => {
      mounted = false;
      sub.remove();
    };
  }, [setting]);

  return enabled;
}

/** iOS Settings > Accessibility > Motion > Reduce Motion. */
export function useReduceMotion(): boolean {
  return useAccessibilitySetting('reduceMotion');
}

/** iOS Settings > Accessibility > Display & Text Size > Reduce Transparency. */
export function useReduceTransparency(): boolean {
  return useAccessibilitySetting('reduceTransparency');
}
