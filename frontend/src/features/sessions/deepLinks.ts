import { Linking } from 'react-native';

export interface TrackerConfig {
  id: string;
  appName: string;
  primarySchemeTemplate: string | null;
  fallbackUrlTemplate: string | null;
  isGuidedFallbackOnly: boolean;
  instructionText: string;
}

export const TRACKER_REGISTRY: Record<string, TrackerConfig> = {
  youtube: {
    id: 'youtube',
    appName: 'YouTube',
    primarySchemeTemplate: 'youtube://watch?v={external_id}',
    fallbackUrlTemplate: 'https://www.youtube.com/watch?v={external_id}',
    isGuidedFallbackOnly: false,
    instructionText: 'Open YouTube to start playing your queued video',
  },
  spotify: {
    id: 'spotify',
    appName: 'Spotify',
    primarySchemeTemplate: 'spotify://',
    fallbackUrlTemplate: 'https://open.spotify.com',
    isGuidedFallbackOnly: false,
    instructionText: 'Open Spotify to start playing your workout playlist',
  },
  apple_fitness: {
    id: 'apple_fitness',
    appName: 'Apple Fitness (Apple Watch)',
    primarySchemeTemplate: null,
    fallbackUrlTemplate: null,
    isGuidedFallbackOnly: true,
    instructionText: 'Start your workout session on your Apple Watch or Fitness app',
  },
  custom: {
    id: 'custom',
    appName: 'Custom Workout',
    primarySchemeTemplate: null,
    fallbackUrlTemplate: null,
    isGuidedFallbackOnly: true,
    instructionText: 'Start your activity tracker or timer',
  },
};

export function sanitizeExternalId(externalId?: string): string {
  if (!externalId) return '';
  // Remove control characters, null bytes, and trim whitespace
  const cleaned = externalId.replace(/[\x00-\x1F\x7F-\x9F]/g, '').trim();
  // Encode URI components to prevent deep link injection or query parameter tampering
  return encodeURIComponent(cleaned);
}

export async function launchTrackerApp(
  trackerId: string,
  externalId?: string
): Promise<{ success: boolean; launchedVia: 'primary' | 'fallback' | 'guided'; error?: string }> {
  const config = TRACKER_REGISTRY[trackerId] || TRACKER_REGISTRY.custom;

  if (config.isGuidedFallbackOnly) {
    return { success: true, launchedVia: 'guided' };
  }

  const safeExternalId = sanitizeExternalId(externalId);
  const primaryUrl = config.primarySchemeTemplate
    ? config.primarySchemeTemplate.replace('{external_id}', safeExternalId)
    : null;
  const fallbackUrl = config.fallbackUrlTemplate
    ? config.fallbackUrlTemplate.replace('{external_id}', safeExternalId)
    : null;


  if (primaryUrl) {
    try {
      const canOpen = await Linking.canOpenURL(primaryUrl);
      if (canOpen) {
        await Linking.openURL(primaryUrl);
        return { success: true, launchedVia: 'primary' };
      }
    } catch {
      // Primary scheme check failed, try fallback below
    }
  }

  if (fallbackUrl) {
    try {
      const canOpenFallback = await Linking.canOpenURL(fallbackUrl);
      if (canOpenFallback) {
        await Linking.openURL(fallbackUrl);
        return { success: true, launchedVia: 'fallback' };
      }
    } catch {
      // Fallback check failed
    }
  }

  return {
    success: false,
    launchedVia: 'fallback',
    error: `Unable to launch ${config.appName}. Please open the app manually.`,
  };
}
