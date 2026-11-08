import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  AppState,
  AppStateStatus,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from '@/core/components/Text';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { launchTrackerApp, mediaTargetForContent } from '@/features/sessions/deepLinks';
import { useSessionStore } from '@/features/sessions/sessionStore';

export default function SessionHandoffScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id: routeSessionId } = useLocalSearchParams<{ id: string }>();

  const {
    currentSession,
    currentStep,
    isLoading,
    mediaError,
    error,
    errorCode,
    skipTrackerStep,
    advanceStep,
    startCurrentSession,
    checkActiveSession,
    completeCurrentSession,
    abandonCurrentSession,
    discardCurrentSession,
  } = useSessionStore();

  const [trackerLaunched, setTrackerLaunched] = useState(false);
  const [trackerError, setTrackerError] = useState<string | null>(null);
  const [isResolving, setIsResolving] = useState(
    () => !currentSession || currentSession.id !== routeSessionId
  );

  // Progress persists across force-quits (SPEC §6.2): if the store doesn't already hold
  // this route's session (cold start, deep link), rebuild it from the server.
  useEffect(() => {
    if (currentSession && currentSession.id === routeSessionId) {
      setIsResolving(false);
      return;
    }
    let cancelled = false;
    checkActiveSession().finally(() => {
      if (!cancelled) setIsResolving(false);
    });
    return () => {
      cancelled = true;
    };
    // Only re-resolve when the route changes, not on every store update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSessionId]);

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
    const { provider, externalId } = mediaTargetForContent(currentSession?.content_id);
    await startCurrentSession(provider, externalId);
  };

  const handleComplete = async () => {
    if (await completeCurrentSession()) router.replace('/(app)/history');
  };

  const handleAbandon = async () => {
    if (await abandonCurrentSession()) router.replace('/(app)');
  };

  const handleDiscard = async () => {
    if (await discardCurrentSession()) router.replace('/(app)');
  };

  const isPending = currentSession?.status === 'pending';
  const isInProgress = currentSession?.status === 'in_progress';
  const transitionError =
    errorCode === 'SESSION_NOT_STARTED'
      ? 'Open your media first (step 2), or discard this session.'
      : error;

  if (isResolving) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator color={colors.heatCore} accessibilityLabel="Loading session" />
      </View>
    );
  }

  if (!currentSession || currentSession.id !== routeSessionId) {
    return (
      <View style={[styles.container, styles.centered, { paddingHorizontal: spacing.lg }]}>
        <Text style={styles.title} accessibilityRole="header">
          Session not found
        </Text>
        <Text style={styles.subtitle}>
          This session has ended or belongs to another account.
        </Text>
        <TouchableOpacity
          style={[styles.doneButton, { marginTop: spacing.lg }]}
          onPress={() => router.replace('/(app)')}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel="Return to Queue Screen"
        >
          <Text style={styles.buttonText}>Return to Queue</Text>
        </TouchableOpacity>
      </View>
    );
  }

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
          <Text style={styles.title} accessibilityRole="header">
            Workout Handoff
          </Text>
          <Text style={styles.subtitle}>
            Guided 4-step setup for your active workout session
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
        <View style={[styles.stepCard, currentStep === 1 && styles.activeStepCard]}>
          {/* The step summary sits on the header, not the card: an accessible card would hide
              the step's buttons from VoiceOver. */}
          <View
            style={styles.stepHeader}
            accessible={true}
            accessibilityRole="header"
            accessibilityLabel={`Step 1 of 4: Start Activity Tracker. ${currentStep > 1 ? 'Completed or skipped' : 'Active step'}`}
          >
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
              <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                <Ionicons name="checkmark-circle" size={16} color={colors.signalVerified} />
              </View>
              <Text style={styles.completedBadge}>Completed / Skipped</Text>
            </View>
          )}
        </View>

        {/* Step 2 Card: Media Launch & Server Start */}
        <View style={[styles.stepCard, currentStep === 2 && styles.activeStepCard]}>
          {/* The step summary sits on the header, not the card: an accessible card would hide
              the step's buttons from VoiceOver. */}
          <View
            style={styles.stepHeader}
            accessible={true}
            accessibilityRole="header"
            accessibilityLabel={`Step 2 of 4: Launch Media and Start Session. ${currentStep > 2 ? 'Session Started' : currentStep === 2 ? 'Active step' : 'Pending'}`}
          >
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
              accessibilityState={{ disabled: isLoading, busy: isLoading }}
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
              <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                <Ionicons name="checkmark-circle" size={16} color={colors.signalVerified} />
              </View>
              <Text style={styles.completedBadge}>Session Started</Text>
            </View>
          )}
        </View>

        {/* Step 3 Card: Session Target End Time */}
        <View style={[styles.stepCard, currentStep === 3 && styles.activeStepCard]}>
          <View
            style={styles.stepHeader}
            accessible={true}
            accessibilityRole="header"
            accessibilityLabel={`Step 3 of 4: Session In Progress. ${currentStep === 3 ? `Target end time is ${formatTargetEndTime()}` : 'Pending step 2 completion'}`}
          >
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

        {/* Step 4 Card: Mark Complete (SPEC §6.2) */}
        <View style={[styles.stepCard, currentStep === 3 && styles.activeStepCard]}>
          <View
            style={styles.stepHeader}
            accessible={true}
            accessibilityRole="header"
            accessibilityLabel="Step 4 of 4: Mark Complete"
          >
            <Text style={styles.stepNumber}>4</Text>
            <Text style={styles.stepTitle}>Mark Complete</Text>
          </View>
          <Text style={styles.stepDescription}>
            Finished? Completing removes this content from your queue.
          </Text>

          {transitionError ? (
            <Text style={styles.errorText} accessibilityRole="alert">
              {transitionError}
            </Text>
          ) : null}

          <TouchableOpacity
            style={[styles.primaryButton, (!isInProgress || isLoading) && styles.disabledButton]}
            onPress={handleComplete}
            disabled={!isInProgress || isLoading}
            activeOpacity={0.8}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Mark session complete"
            accessibilityState={{ disabled: !isInProgress || isLoading }}
          >
            <Text style={styles.buttonText}>Mark Complete</Text>
          </TouchableOpacity>

          <View style={[styles.buttonRow, { marginTop: spacing.sm }]}>
            {isPending ? (
              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={handleDiscard}
                disabled={isLoading}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Discard session"
                accessibilityHint="Deletes this session before it starts"
              >
                <Text style={styles.secondaryButtonText}>Discard</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={handleAbandon}
                disabled={isLoading}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Abandon session"
                accessibilityHint="Ends the session without consuming the content"
              >
                <Text style={styles.secondaryButtonText}>Abandon</Text>
              </TouchableOpacity>
            )}
          </View>
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
  centered: {
    alignItems: 'center',
    justifyContent: 'center',
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
