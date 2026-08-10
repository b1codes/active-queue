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
import { useRouter } from 'expo-router';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { launchTrackerApp } from '@/features/sessions/deepLinks';
import { useSessionStore } from '@/features/sessions/sessionStore';

export default function SessionHandoffScreen() {
  const router = useRouter();

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
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      <View style={styles.header}>
        <Text style={styles.title}>Workout Handoff</Text>
        <Text style={styles.subtitle}>
          Guided 3-step setup for your active workout session
        </Text>
      </View>

      {currentSession && (
        <View style={styles.badgeCard}>
          <Text style={styles.badgeText}>
            {currentSession.activity_id.toUpperCase()} • {formatDurationLabel(currentSession.duration_seconds)}
          </Text>
        </View>
      )}

      {/* Step 1 Card: Tracker Handoff */}
      <View style={[styles.stepCard, currentStep === 1 && styles.activeStepCard]}>
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
            >
              <Text style={styles.buttonText}>Open Tracker</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={skipTrackerStep}
              activeOpacity={0.8}
            >
              <Text style={styles.secondaryButtonText}>Skip Step</Text>
            </TouchableOpacity>
          </View>
        )}
        {currentStep > 1 && <Text style={styles.completedBadge}>✓ Completed / Skipped</Text>}
      </View>

      {/* Step 2 Card: Media Launch & Server Start */}
      <View style={[styles.stepCard, currentStep === 2 && styles.activeStepCard]}>
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
            <TouchableOpacity style={styles.retryButton} onPress={handleLaunchMedia}>
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
          >
            {isLoading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.buttonText}>Launch Media & Start Session</Text>
            )}
          </TouchableOpacity>
        )}
        {currentStep > 2 && <Text style={styles.completedBadge}>✓ Session Started</Text>}
      </View>

      {/* Step 3 Card: Session Target End Time */}
      <View style={[styles.stepCard, currentStep === 3 && styles.activeStepCard]}>
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
            >
              <Text style={styles.buttonText}>Return to Queue</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <Text style={styles.pendingText}>Pending media launch in Step 2...</Text>
        )}
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
    paddingTop: spacing.xl,
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
  completedBadge: {
    color: colors.signalVerified,
    fontWeight: '600',
    marginTop: spacing.xs,
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
    paddingHorizontal: spacing.sm,
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
    backgroundColor: colors.heatCore,
    borderRadius: rounded.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  pendingText: {
    ...typography.body,
    color: colors.inkSecondary,
    fontStyle: 'italic',
  },
});
