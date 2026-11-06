import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { NoDurationMatchState } from '@/core/components/states';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { ApiError } from '@/core/api/apiClient';
import { matchContent, type ContentMatchResult } from '@/features/matching/matchingApi';
import { useSessionStore } from '@/features/sessions/sessionStore';

/**
 * Content-first matching (SPEC §5.2): given a queued item, show which catalog activities
 * its duration fits and create a session for the one the user picks.
 */
export default function MatchScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { contentId } = useLocalSearchParams<{ contentId: string }>();
  const { createNewSession, isLoading, error, errorCode, conflictSessionId } = useSessionStore();

  const [match, setMatch] = useState<ContentMatchResult | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!contentId) return;
    setLoadError(null);
    setMatch(null);
    try {
      const result = await matchContent(contentId);
      setMatch(result);
      setSelected(result.matching_activities[0]?.id ?? null);
    } catch (err: unknown) {
      setLoadError(
        err instanceof ApiError && err.code === 'CONTENT_NOT_FOUND'
          ? 'This item is no longer in your queue.'
          : err instanceof Error
            ? err.message
            : 'Could not load matching activities.'
      );
    }
  }, [contentId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStart = async () => {
    if (!selected || !contentId) return;
    const session = await createNewSession({
      activity_id: selected,
      match_mode: 'content_first',
      content_id: contentId,
    });
    if (session) {
      router.push({ pathname: '/(app)/session/[id]', params: { id: session.id } });
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[
        styles.content,
        { paddingTop: Math.max(insets.top, spacing.xl), paddingBottom: spacing.xl },
      ]}
    >
      <Text style={styles.title} accessibilityRole="header">
        Pick an activity
      </Text>

      {!match && !loadError ? (
        <ActivityIndicator color={colors.heatCore} accessibilityLabel="Loading matches" />
      ) : null}

      {loadError ? (
        <View accessible={true} accessibilityRole="alert">
          <Text style={styles.errorText}>{loadError}</Text>
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={load}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Retry loading matches"
          >
            <Text style={styles.secondaryButtonText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {match && !match.is_valid ? (
        <NoDurationMatchState
          durationLabel={match.duration_label}
          rejectionReason={match.rejection_reason ?? undefined}
          onResetPress={() => router.back()}
        />
      ) : null}

      {match && match.is_valid ? (
        <>
          <Text style={styles.subtitle}>
            This item runs {match.duration_label}. These activities fit that length:
          </Text>
          <View accessibilityRole="radiogroup">
            {match.matching_activities.map((act) => {
              const isSelected = act.id === selected;
              return (
                <TouchableOpacity
                  key={act.id}
                  style={[styles.option, isSelected && styles.optionSelected]}
                  onPress={() => setSelected(act.id)}
                  accessible={true}
                  accessibilityRole="radio"
                  accessibilityLabel={act.name}
                  accessibilityState={{ checked: isSelected }}
                >
                  <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>
                    {act.name}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {error ? (
            <View accessible={true} accessibilityRole="alert" style={styles.errorBox}>
              <Text style={styles.errorText}>
                {errorCode === 'ACTIVE_SESSION_EXISTS'
                  ? 'You already have a session in progress.'
                  : error}
              </Text>
              {conflictSessionId ? (
                <TouchableOpacity
                  style={styles.secondaryButton}
                  onPress={() =>
                    router.push({
                      pathname: '/(app)/session/[id]',
                      params: { id: conflictSessionId },
                    })
                  }
                  accessible={true}
                  accessibilityRole="button"
                  accessibilityLabel="Resume active session"
                >
                  <Text style={styles.secondaryButtonText}>Resume active session</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          ) : null}

          <TouchableOpacity
            style={[styles.primaryButton, (!selected || isLoading) && styles.disabled]}
            onPress={handleStart}
            disabled={!selected || isLoading}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Start session"
            accessibilityState={{ disabled: !selected || isLoading }}
          >
            {isLoading ? (
              <ActivityIndicator color={colors.void} />
            ) : (
              <Text style={styles.primaryButtonText}>Start session</Text>
            )}
          </TouchableOpacity>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.void,
    flex: 1,
  },
  content: {
    alignSelf: 'center',
    gap: spacing.md,
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    width: '100%',
  },
  title: {
    ...typography.headline,
    color: colors.ink,
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
  },
  option: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    marginBottom: spacing.sm,
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  optionSelected: {
    backgroundColor: colors.heatCore,
    borderColor: colors.heatCore,
  },
  optionText: {
    ...typography.body,
    color: colors.ink,
  },
  optionTextSelected: {
    color: colors.void,
    fontWeight: '600',
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.heatCore,
    borderRadius: rounded.md,
    justifyContent: 'center',
    minHeight: 48,
  },
  primaryButtonText: {
    ...typography.label,
    color: colors.void,
    fontWeight: '700',
  },
  secondaryButton: {
    alignItems: 'center',
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    justifyContent: 'center',
    marginTop: spacing.sm,
    minHeight: 44,
    paddingHorizontal: spacing.md,
  },
  secondaryButtonText: {
    ...typography.label,
    color: colors.ink,
  },
  disabled: {
    opacity: 0.5,
  },
  errorBox: {
    gap: spacing.xs,
  },
  errorText: {
    ...typography.body,
    color: colors.heatCorona,
  },
});
