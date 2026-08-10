import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  AppState,
  AppStateStatus,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { launchTrackerApp } from '@/features/sessions/deepLinks';
import { useSessionStore } from '@/features/sessions/sessionStore';

export default function SessionHandoffScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const {
    currentSession,
    currentStep,
    isLoading,
    mediaError,
    skipTrackerStep,
    advanceStep,
    startCurrentSession,
  } = useSessionStore();

  const [trackerLaunched, setTrackerLaunched] = useState(false);
  const [trackerError, setTrackerError] = useState<string | null>(null);

  // AppState foreground detection per SPEC §6.2
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      if (nextAppState === 'active') {
        if (trackerLaunched && currentStep === 1) {
          advanceStep();
        }
      }
    });

    return () => {
      subscription.remove();
    };
  }, [trackerLaunched, currentStep, advanceStep]);

  const handleLaunchTracker = async () => {
    setTrackerError(null);
    const trackerId = currentSession?.activity_id === 'running' ? 'apple_fitness' : 'custom';
    const res = await launchTrackerApp(trackerId);

    if (res.success) {
      setTrackerLaunched(true);
      advanceStep();
    } else {
      setTrackerError(res.error || 'Failed to launch tracker app');
    }
  };

  const handleLaunchMedia = async () => {
    const provider = currentSession?.content_id?.split(':')[0] === 'yt' ? 'youtube' : 'spotify';
    const externalId = currentSession?.content_id?.split(':')[1];
    await startCurrentSession(provider, externalId);
  };

  // Format computed target end time label (SPEC §6.2: label, not live timer)
  const formatTargetEndTime = (): string => {
    if (!currentSession?.started_at) return 'N/A';
    const startDate = new Date(currentSession.started_at);
    const endDate = new Date(startDate.getTime() + currentSession.duration_seconds * 1000);
    return endDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDurationLabel = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[
        styles.contentContainer,
        { paddingTop: Math.max(insets.top, spacing.xl), paddingBottom: Math.max(insets.bottom, spacing.xl) },
      ]}
    >
      <View style={styles.cardWrapper}>
        <View style={styles.header}>
          <Text style={styles.title}>Workout Handoff</Text>
          <Text style={styles.subtitle}>
            Guided 3-step setup for your active workout session
          </Text>
        </View>

        {currentSession && (
          <View
            style={styles.badgeCard}
            accessible={true}
            accessibilityLabel={`Selected activity: ${currentSession.activity_id}, duration: ${formatDurationLabel(currentSession.duration_seconds)}`}
          >
            <Text style={styles.badgeText}>
              {currentSession.activity_id.toUpperCase()} • {formatDurationLabel(currentSession.duration_seconds)}
            </Text>
          </View>
        )}

        {/* Step 1 Card: Tracker Handoff */}
        <View
          style={[styles.stepCard, currentStep === 1 && styles.activeStepCard]}
          accessible={true}
          accessibilityLabel={`Step 1 of 3: Start Activity Tracker. ${currentStep > 1 ? 'Completed or skipped' : 'Active step'}`}
        >
          <View style={styles.stepHeader}>
            <Text style={styles.stepNumber}>1</Text>
            <Text style={styles.stepTitle}>Start Activity Tracker</Text>
          </View>
          <Text style={styles.stepDescription}>
            Open your fitness app or Apple Watch to record physical metrics. (Skippable)
          </Text>

          {trackerError && <Text style={styles.errorText}>{trackerError}</Text>}

          {currentStep === 1 && (
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={styles.primaryButton}
                onPress={handleLaunchTracker}
                activeOpacity={0.8}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Open Tracker App"
                accessibilityHint="Launches your selected workout tracking app or displays guide"
              >
                <Text style={styles.buttonText}>Open Tracker</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={skipTrackerStep}
                activeOpacity={0.8}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Skip Tracker Step"
                accessibilityHint="Proceed directly to launching media"
              >
                <Text style={styles.secondaryButtonText}>Skip Step</Text>
              </TouchableOpacity>
            </View>
          )}
          {currentStep > 1 && (
            <View style={styles.completedBadgeRow}>
              <Ionicons name="checkmark-circle" size={16} color={colors.signalVerified} />
              <Text style={styles.completedBadge}>Completed / Skipped</Text>
            </View>
          )}
        </View>

        {/* Step 2 Card: Media Launch & Server Start */}
        <View
          style={[styles.stepCard, currentStep === 2 && styles.activeStepCard]}
          accessible={true}
          accessibilityLabel={`Step 2 of 3: Launch Media and Start Session. ${currentStep > 2 ? 'Session Started' : currentStep === 2 ? 'Active step' : 'Pending'}`}
        >
          <View style={styles.stepHeader}>
            <Text style={styles.stepNumber}>2</Text>
            <Text style={styles.stepTitle}>Launch Media & Start Session</Text>
          </View>
          <Text style={styles.stepDescription}>
            Launch media playback and record session start on server.
          </Text>

          {mediaError && (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{mediaError}</Text>
              <TouchableOpacity
                style={styles.retryButton}
                onPress={handleLaunchMedia}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Retry media launch"
              >
                <Text style={styles.retryButtonText}>Retry</Text>
              </TouchableOpacity>
            </View>
          )}

          {currentStep === 2 && (
            <TouchableOpacity
              style={[styles.primaryButton, isLoading && styles.disabledButton]}
              onPress={handleLaunchMedia}
              disabled={isLoading}
              activeOpacity={0.8}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Launch Media and Start Workout Session"
              accessibilityHint="Launches target media player app and starts session timestamp on server"
            >
              {isLoading ? (
                <ActivityIndicator color={colors.void} />
              ) : (
                <Text style={styles.buttonText}>Launch Media & Start Session</Text>
              )}
            </TouchableOpacity>
          )}
          {currentStep > 2 && (
            <View style={styles.completedBadgeRow}>
              <Ionicons name="checkmark-circle" size={16} color={colors.signalVerified} />
              <Text style={styles.completedBadge}>Session Started</Text>
            </View>
          )}
        </View>

        {/* Step 3 Card: Session Target End Time */}
        <View
          style={[styles.stepCard, currentStep === 3 && styles.activeStepCard]}
          accessible={true}
          accessibilityLabel={`Step 3 of 3: Session In Progress. ${currentStep === 3 ? `Target end time is ${formatTargetEndTime()}` : 'Pending step 2 completion'}`}
        >
          <View style={styles.stepHeader}>
            <Text style={styles.stepNumber}>3</Text>
            <Text style={styles.stepTitle}>Session In Progress</Text>
          </View>

          {currentStep === 3 ? (
            <View style={styles.targetTimeContainer}>
              <Text style={styles.targetTimeLabel}>Workout Target End Time</Text>
              <Text style={styles.targetTimeValue}>{formatTargetEndTime()}</Text>
              <Text style={styles.infoText}>
                ActiveQueue handoff is complete. You can now minimize the app and enjoy your workout.
              </Text>
              <TouchableOpacity
                style={styles.doneButton}
                onPress={() => router.replace('/(app)')}
                activeOpacity={0.8}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Return to Queue Screen"
              >
                <Text style={styles.buttonText}>Return to Queue</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <Text style={styles.pendingText}>Pending media launch in Step 2...</Text>
          )}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.void,
    flex: 1,
  },
  contentContainer: {
    padding: spacing.lg,
  },
  cardWrapper: {
    alignSelf: 'center',
    maxWidth: 680,
    width: '100%',
  },
  header: {
    marginBottom: spacing.lg,
  },
  title: {
    ...typography.title,
    color: colors.ink,
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    marginTop: spacing.xs,
  },
  badgeCard: {
    alignSelf: 'flex-start',
    backgroundColor: colors.substrate,
    borderRadius: rounded.md,
    marginBottom: spacing.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  badgeText: {
    color: colors.heatCore,
    fontWeight: '600',
  },
  stepCard: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  activeStepCard: {
    borderColor: colors.heatCore,
  },
  stepHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: spacing.xs,
  },
  stepNumber: {
    color: colors.heatCore,
    fontSize: 18,
    fontWeight: 'bold',
    marginRight: spacing.sm,
  },
  stepTitle: {
    ...typography.subtitle,
    color: colors.ink,
  },
  stepDescription: {
    ...typography.body,
    color: colors.inkSecondary,
    marginBottom: spacing.md,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.sm,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  buttonText: {
    ...typography.label,
    color: colors.void,
    fontWeight: '600',
  },
  secondaryButton: {
    alignItems: 'center',
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  secondaryButtonText: {
    ...typography.label,
    color: colors.inkSecondary,
  },
  disabledButton: {
    opacity: 0.6,
  },
  completedBadgeRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
    marginTop: spacing.xs,
  },
  completedBadge: {
    color: colors.signalVerified,
    fontWeight: '600',
  },
  errorContainer: {
    marginBottom: spacing.md,
  },
  errorText: {
    color: colors.heatCore,
    marginBottom: spacing.xs,
  },
  retryButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.sm,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  retryButtonText: {
    ...typography.label,
    color: colors.void,
  },
  targetTimeContainer: {
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  targetTimeLabel: {
    ...typography.body,
    color: colors.inkSecondary,
  },
  targetTimeValue: {
    color: colors.heatCore,
    fontSize: 28,
    fontWeight: 'bold',
    marginVertical: spacing.xs,
  },
  infoText: {
    ...typography.body,
    color: colors.inkSecondary,
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  doneButton: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.sm,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    width: '100%',
  },
  pendingText: {
    ...typography.body,
    color: colors.inkSecondary,
    fontStyle: 'italic',
  },
});
