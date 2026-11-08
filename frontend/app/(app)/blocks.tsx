import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from '@/core/components/Text';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GlassHeader, useGlassHeaderHeight, ThermalGlowTouchable } from '@/core/components';
import { NoDurationMatchState } from '@/core/components/states';
import { colors, fontScale, rounded, spacing, typography } from '@/core/theme';
import {
  listActivities,
  listTimeBlocks,
  matchTimeBlock,
  type Activity,
  type TimeBlock,
  type TimeMatchResult,
} from '@/features/matching/matchingApi';
import { useSessionStore } from '@/features/sessions/sessionStore';

const DEFAULT_BLOCK_SECONDS = 1800;

function tabular(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  return `${mins}:${String(seconds % 60).padStart(2, '0')}`;
}

/**
 * Time-first flow (SPEC §5.3): pick a time block and an activity that fits it, then the
 * server proposes queued media inside the asymmetric [B, B+300] / [B-120, B) windows.
 * Starting creates a time_first session, with the chosen media or as a bare timer.
 */
export default function BlocksScreen() {
  const router = useRouter();
  const [headerHeight, setHeaderHeight] = useGlassHeaderHeight();
  const { createNewSession, isLoading: isCreating, error: createError, errorCode, conflictSessionId } =
    useSessionStore();

  const [blocks, setBlocks] = useState<TimeBlock[] | null>(null);
  const [activities, setActivities] = useState<Activity[] | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number>(DEFAULT_BLOCK_SECONDS);
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null);
  const [match, setMatch] = useState<TimeMatchResult | null>(null);
  const [isMatching, setIsMatching] = useState(false);

  const loadCatalog = useCallback(async () => {
    setCatalogError(null);
    try {
      const [tb, acts] = await Promise.all([listTimeBlocks(), listActivities()]);
      setBlocks(tb);
      setActivities(acts.filter((a) => a.is_active));
    } catch (err: unknown) {
      setCatalogError(err instanceof Error ? err.message : 'Could not load time blocks');
    }
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  // Only offer activities whose catalog bounds accept the chosen block; the server would
  // reject anything else with ACTIVITY_DURATION_MISMATCH.
  const fittingActivities = useMemo(
    () =>
      (activities ?? []).filter(
        (a) => a.min_duration_seconds <= selectedDuration && selectedDuration <= a.max_duration_seconds
      ),
    [activities, selectedDuration]
  );

  useEffect(() => {
    if (!fittingActivities.some((a) => a.id === selectedActivity)) {
      setSelectedActivity(fittingActivities[0]?.id ?? null);
    }
  }, [fittingActivities, selectedActivity]);

  useEffect(() => {
    let cancelled = false;
    setIsMatching(true);
    matchTimeBlock(selectedDuration)
      .then((res) => {
        if (!cancelled) setMatch(res);
      })
      .catch(() => {
        if (!cancelled) setMatch(null);
      })
      .finally(() => {
        if (!cancelled) setIsMatching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDuration]);

  const start = async (contentId: string | null) => {
    if (!selectedActivity) return;
    const session = await createNewSession({
      activity_id: selectedActivity,
      match_mode: 'time_first',
      content_id: contentId,
      target_duration_seconds: contentId ? null : selectedDuration,
    });
    if (session) {
      router.push({ pathname: '/(app)/session/[id]', params: { id: session.id } });
    }
  };

  const topItem = match?.matched_items[0] ?? null;

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingTop: headerHeight + spacing.lg }]}
        showsVerticalScrollIndicator={false}
      >
        {catalogError ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle} accessibilityRole="header">
              Couldn&apos;t load time blocks
            </Text>
            <Text style={styles.emptyBody} accessibilityRole="alert">
              {catalogError}
            </Text>
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={loadCatalog}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Retry loading time blocks"
            >
              <Text style={styles.secondaryButtonText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : null}

        {!blocks && !catalogError ? (
          <ActivityIndicator color={colors.heatCore} accessibilityLabel="Loading time blocks" />
        ) : null}

        {blocks ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle} accessibilityRole="header">Select Workout Duration</Text>
            <View style={styles.presetGrid} accessibilityRole="radiogroup">
              {blocks.map((block) => {
                const isSelected = selectedDuration === block.duration_seconds;
                return (
                  <TouchableOpacity
                    key={block.id}
                    style={[
                      styles.durationButton,
                      isSelected ? styles.durationButtonSelected : styles.durationButtonUnselected,
                    ]}
                    onPress={() => setSelectedDuration(block.duration_seconds)}
                    activeOpacity={0.85}
                    accessible={true}
                    accessibilityRole="radio"
                    accessibilityLabel={`Target duration ${block.label}`}
                    accessibilityState={{ checked: isSelected }}
                  >
                    <Text
                      style={[
                        styles.durationButtonText,
                        isSelected ? styles.durationButtonTextSelected : styles.durationButtonTextUnselected,
                      ]}
                    >
                      {tabular(block.duration_seconds)}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        ) : null}

        {activities ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle} accessibilityRole="header">Activity Type</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipRow}
              accessibilityRole="radiogroup"
            >
              {fittingActivities.map((act) => {
                const isSelected = selectedActivity === act.id;
                return (
                  <TouchableOpacity
                    key={act.id}
                    style={[styles.chip, isSelected ? styles.chipSelected : styles.chipUnselected]}
                    onPress={() => setSelectedActivity(act.id)}
                    activeOpacity={0.85}
                    accessible={true}
                    accessibilityRole="radio"
                    accessibilityLabel={`Activity ${act.name}`}
                    accessibilityState={{ checked: isSelected }}
                  >
                    <Text
                      style={[styles.chipText, isSelected ? styles.chipTextSelected : styles.chipTextUnselected]}
                    >
                      {act.name}
                    </Text>
                    {isSelected ? <Ionicons name="checkmark" size={14} color={colors.void} /> : null}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        ) : null}

        {blocks && activities ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle} accessibilityRole="header">Matched Media</Text>

            {createError ? (
              <View>
                <Text style={styles.emptyBody} accessibilityRole="alert">
                  {errorCode === 'ACTIVE_SESSION_EXISTS'
                    ? 'You already have a session in progress.'
                    : createError}
                </Text>
                {conflictSessionId ? (
                  <TouchableOpacity
                    style={styles.secondaryButton}
                    onPress={() =>
                      router.push({ pathname: '/(app)/session/[id]', params: { id: conflictSessionId } })
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

            {isMatching ? (
              <ActivityIndicator color={colors.heatCore} accessibilityLabel="Finding media" />
            ) : topItem ? (
              <View style={styles.matchCard}>
                <View style={styles.matchHeader}>
                  <View style={styles.matchBadge}>
                    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                      <Ionicons name="sparkles" size={14} color={colors.heatCore} />
                    </View>
                    <Text style={styles.matchBadgeText}>
                      {match?.window_type === 'fallback' ? 'Slightly shorter' : 'Fits'} {tabular(selectedDuration)}
                    </Text>
                  </View>
                  <View style={styles.durationPillMatched}>
                    <Text style={styles.durationTextMatched} maxFontSizeMultiplier={fontScale.compact}>
                      {topItem.duration_label}
                    </Text>
                  </View>
                </View>

                <Text style={styles.itemTitle} numberOfLines={2}>
                  {topItem.title}
                </Text>
                <Text style={styles.itemMeta}>Provider: {topItem.provider.toUpperCase()}</Text>

                <ThermalGlowTouchable
                  testID="start-matched-session"
                  style={[styles.startButton, (!selectedActivity || isCreating) && { opacity: 0.5 }]}
                  onPress={() => start(topItem.content_id)}
                  disabled={!selectedActivity || isCreating}
                  borderRadius={rounded.md}
                  accessible={true}
                  accessibilityRole="button"
                  accessibilityLabel="Start session with matched media"
                >
                  <Text style={styles.startButtonText}>Start Session ({tabular(selectedDuration)})</Text>
                </ThermalGlowTouchable>
              </View>
            ) : (
              <NoDurationMatchState
                durationLabel={tabular(selectedDuration)}
                rejectionReason="no_content_in_window"
              />
            )}

            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={() => start(null)}
              disabled={!selectedActivity || isCreating}
              activeOpacity={0.85}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Start a timer-only session"
              accessibilityHint="Starts the time block without any media"
              accessibilityState={{ disabled: !selectedActivity || isCreating }}
            >
              <Text style={styles.secondaryButtonText}>Timer only (no media)</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </ScrollView>

      <GlassHeader
        title="Time Blocks"
        subtitle="Time-first activity & runtime orchestrator"
        onHeightChange={setHeaderHeight}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.void,
    flex: 1,
  },
  headerBorder: {
    borderBottomColor: colors.glassEdge,
    borderBottomWidth: 1,
    width: '100%',
  },
  header: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    width: '100%',
  },
  title: {
    ...typography.headline,
    color: colors.ink,
  },
  subtitle: {
    ...typography.bodySm,
    color: colors.inkMuted,
    marginTop: 2,
  },
  scrollContent: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    gap: spacing.xl,
    width: '100%',
  },
  section: {
    gap: spacing.md,
  },
  sectionTitle: {
    ...typography.subtitle,
    color: colors.ink,
    fontSize: 16,
  },
  presetGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  durationButton: {
    borderRadius: rounded.sm,
    borderWidth: 1,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    alignItems: 'center',
    flexBasis: '30%',
    flexGrow: 1,
  },
  durationButtonUnselected: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecular,
  },
  durationButtonSelected: {
    backgroundColor: colors.lensFlatRaised,
    borderColor: colors.heatCore,
  },
  durationButtonText: {
    ...typography.duration,
    fontSize: 15,
  },
  durationButtonTextUnselected: {
    color: colors.inkSecondary,
  },
  durationButtonTextSelected: {
    color: colors.heatCoreInk,
    fontWeight: '700',
  },
  chipRow: {
    gap: spacing.xs,
  },
  chip: {
    minHeight: 44,
    borderRadius: rounded.pill,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  chipUnselected: {
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderWidth: 1,
  },
  // Selection is an inversion per DESIGN.md §5 Chip Activity Selected
  chipSelected: {
    backgroundColor: colors.ink,
  },
  chipText: {
    ...typography.label,
    fontSize: 13,
  },
  chipTextUnselected: {
    color: colors.inkSecondary,
  },
  chipTextSelected: {
    color: colors.void,
    fontWeight: '600',
  },
  matchCard: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecularLight,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.lg,
    gap: spacing.md,
  },
  matchHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  matchBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  matchBadgeText: {
    ...typography.label,
    color: colors.inkSecondary,
    fontSize: 12,
  },
  durationPillMatched: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.pill,
    minHeight: 24,
    paddingHorizontal: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  durationTextMatched: {
    ...typography.duration,
    color: colors.void,
    fontSize: 13,
    fontWeight: '700',
  },
  itemTitle: {
    ...typography.title,
    color: colors.ink,
    fontSize: 18,
    lineHeight: 24,
  },
  itemMeta: {
    ...typography.bodySm,
    color: colors.inkMuted,
  },
  startButton: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.md,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.xs,
  },
  startButtonText: {
    ...typography.subtitle,
    color: colors.void, // Black Label Rule
    fontWeight: '700',
  },
  emptyCard: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.md,
  },
  emptyTitle: {
    ...typography.title,
    color: colors.ink,
    textAlign: 'center',
    fontSize: 18,
  },
  emptyBody: {
    ...typography.body,
    color: colors.inkMuted,
    textAlign: 'center',
    fontSize: 14,
    lineHeight: 20,
  },
  secondaryButton: {
    backgroundColor: colors.lensFlatRaised,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    height: 48,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  secondaryButtonText: {
    ...typography.subtitle,
    color: colors.ink,
    fontSize: 14,
  },
});

