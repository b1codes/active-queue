import { Linking } from 'react-native';
import { launchTrackerApp, TRACKER_REGISTRY } from '../features/sessions/deepLinks';

jest.mock('react-native', () => ({
  Linking: {
    canOpenURL: jest.fn(),
    openURL: jest.fn(),
  },
}));

describe('Deep Link Tracker Registry & Launcher', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('TRACKER_REGISTRY contains all 4 expected trackers', () => {
    expect(TRACKER_REGISTRY.youtube).toBeDefined();
    expect(TRACKER_REGISTRY.spotify).toBeDefined();
    expect(TRACKER_REGISTRY.apple_fitness).toBeDefined();
    expect(TRACKER_REGISTRY.custom).toBeDefined();
    expect(TRACKER_REGISTRY.apple_fitness.isGuidedFallbackOnly).toBe(true);
  });

  it('launches YouTube primary scheme when available', async () => {
    (Linking.canOpenURL as jest.Mock).mockResolvedValue(true);
    (Linking.openURL as jest.Mock).mockResolvedValue(true);

    const res = await launchTrackerApp('youtube', 'vid123');

    expect(res.success).toBe(true);
    expect(res.launchedVia).toBe('primary');
    expect(Linking.canOpenURL).toHaveBeenCalledWith('youtube://watch?v=vid123');
    expect(Linking.openURL).toHaveBeenCalledWith('youtube://watch?v=vid123');
  });

  it('falls back to HTTPS URL when primary scheme returns false', async () => {
    (Linking.canOpenURL as jest.Mock)
      .mockResolvedValueOnce(false) // Primary scheme false
      .mockResolvedValueOnce(true); // Fallback URL true
    (Linking.openURL as jest.Mock).mockResolvedValue(true);

    const res = await launchTrackerApp('youtube', 'vid123');

    expect(res.success).toBe(true);
    expect(res.launchedVia).toBe('fallback');
    expect(Linking.openURL).toHaveBeenCalledWith('https://www.youtube.com/watch?v=vid123');
  });

  it('handles apple_fitness guided fallback without deep link attempts', async () => {
    const res = await launchTrackerApp('apple_fitness');

    expect(res.success).toBe(true);
    expect(res.launchedVia).toBe('guided');
    expect(Linking.canOpenURL).not.toHaveBeenCalled();
    expect(Linking.openURL).not.toHaveBeenCalled();
  });
});
