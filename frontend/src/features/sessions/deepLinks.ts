/**
 * Deep Link Registry per SPEC §6.3
 * All primary schemes MUST be registered in app.json ios.infoPlist.LSApplicationQueriesSchemes
 */
export interface DeepLinkEntry {
  key: 'youtube' | 'strava' | 'strong' | 'apple_fitness';
  kind: 'media' | 'tracker';
  primaryScheme: string;
  fallbackUrl: string;
}

export const DEEP_LINK_REGISTRY: Record<string, DeepLinkEntry> = {
  youtube: {
    key: 'youtube',
    kind: 'media',
    primaryScheme: 'vnd.youtube://',
    fallbackUrl: 'https://www.youtube.com',
  },
  strava: {
    key: 'strava',
    kind: 'tracker',
    primaryScheme: 'strava://',
    fallbackUrl: 'https://www.strava.com',
  },
  strong: {
    key: 'strong',
    kind: 'tracker',
    primaryScheme: 'strong://',
    fallbackUrl: 'https://apps.apple.com/app/strong-workout-tracker-gym/id464254477',
  },
  apple_fitness: {
    key: 'apple_fitness',
    kind: 'tracker',
    primaryScheme: '', // Unverified scheme — fallback instructions only per SPEC §6.3
    fallbackUrl: '',
  },
};
