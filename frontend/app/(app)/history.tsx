import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from '@/core/components/Text';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import { GlassHeader, useGlassHeaderHeight } from '@/core/components';
import { colors, fontScale, rounded, spacing, typography } from '@/core/theme';
import { listSessions, type Session } from '@/features/sessions/sessionApi';

const STATUS_META: Record<Session['status'], { label: string; icon: string; color: string }> = {
  completed: { label: 'Completed', icon: 'checkmark-circle', color: colors.signalVerified },
  abandoned: { label: 'Abandoned', icon: 'close-circle-outline', color: colors.inkMuted },
  in_progress: { label: 'In progress', icon: 'play-circle-outline', color: colors.heatCore },
  pending: { label: 'Not started', icon: 'time-outline', color: colors.inkSecondary },
};

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  return `${mins}:${String(seconds % 60).padStart(2, '0')}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Session history (SPEC §9.5): GET /sessions, newest first, cursor-paginated. */
export default function HistoryScreen() {
  const router = useRouter();
  const [headerHeight, setHeaderHeight] = useGlassHeaderHeight();

  const [sessions, setSessions] = useState<Session[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (reset: boolean, after: string | null) => {
    setIsLoading(true);
    setError(null);
    try {
      const page = await listSessions(reset ? null : after);
      setSessions((prev) => (reset ? page.items : [...prev, ...page.items]));
      setCursor(page.next_cursor);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not load history');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Refresh whenever the tab gains focus: a session completed elsewhere should show up.
  useFocusEffect(
    useCallback(() => {
      load(true, null);
    }, [load])
  );

  return (
    <View style={styles.container}>
      <FlatList
        testID="history-list"
        data={sessions}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.listContent, { paddingTop: headerHeight + spacing.lg }]}
        onEndReached={() => {
          if (cursor && !isLoading) load(false, cursor);
        }}
        onEndReachedThreshold={0.5}
        ListHeaderComponent={
          error ? (
            <View style={styles.sessionCard}>
              <Text style={styles.cardTitle} accessibilityRole="header">
                Couldn&apos;t load history
              </Text>
              <Text style={styles.cardMeta} accessibilityRole="alert">
                {error}
              </Text>
              <TouchableOpacity
                style={[styles.primaryButton, { marginTop: spacing.sm }]}
                onPress={() => load(true, null)}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Retry loading history"
              >
                <Text style={styles.primaryButtonText}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : null
        }
        ListFooterComponent={
          isLoading ? (
            <ActivityIndicator color={colors.heatCore} accessibilityLabel="Loading history" />
          ) : null
        }
        renderItem={({ item }) => {
          const meta = STATUS_META[item.status];
          return (
            <View
              style={styles.sessionCard}
              accessible={true}
              accessibilityLabel={`${meta.label} ${item.activity_id} session, ${formatDuration(item.duration_seconds)}, ${formatDate(item.created_at)}`}
            >
              <View style={styles.cardHeader}>
                <View style={styles.verifiedBadge}>
                  <Ionicons name={meta.icon as never} size={18} color={meta.color} />
                  <Text style={[styles.verifiedText, { color: meta.color }]}>{meta.label}</Text>
                </View>
                <View style={styles.durationPill}>
                  <Text style={styles.durationText} maxFontSizeMultiplier={fontScale.compact}>
                    {formatDuration(item.duration_seconds)}
                  </Text>
                </View>
              </View>
              <Text style={styles.cardTitle}>{item.activity_id}</Text>
              <Text style={styles.cardMeta}>
                {formatDate(item.created_at)} · {item.match_mode === 'content_first' ? 'Content first' : 'Time first'}
              </Text>
            </View>
          );
        }}
        ListEmptyComponent={
          isLoading || error ? null : (
            <View style={styles.emptyContainer}>
              <View style={styles.iconCircle} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                <Ionicons name="stats-chart-outline" size={32} color={colors.inkFaint} />
              </View>
              <Text style={styles.emptyTitle}>No Sessions Yet</Text>
              <Text style={styles.emptyBody}>
                Sessions you start from your queue or a time block will be listed here.
              </Text>
              <TouchableOpacity
                style={styles.primaryButton}
                onPress={() => router.push('/(app)/blocks')}
                activeOpacity={0.85}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Start a Time Block Session"
              >
                <Text style={styles.primaryButtonText}>Browse Time Blocks</Text>
              </TouchableOpacity>
            </View>
          )
        }
      />

      <GlassHeader
        title="History"
        subtitle="Your workout & media sessions"
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
  listContent: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    gap: spacing.md,
    width: '100%',
  },
  sessionCard: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecularLight,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.md,
    gap: spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  verifiedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  verifiedText: {
    ...typography.label,
    color: colors.signalVerified,
    fontSize: 13,
  },
  durationPill: {
    backgroundColor: colors.strata,
    borderRadius: rounded.pill,
    minHeight: 24,
    paddingHorizontal: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  durationText: {
    ...typography.duration,
    color: colors.ink,
    fontSize: 13,
  },
  cardTitle: {
    ...typography.title,
    color: colors.ink,
    fontSize: 17,
  },
  cardMeta: {
    ...typography.bodySm,
    color: colors.inkMuted,
    fontSize: 13,
  },
  emptyContainer: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.xxl,
    alignItems: 'center',
    marginTop: spacing.xl,
    gap: spacing.md,
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: rounded.pill,
    backgroundColor: colors.strata,
    alignItems: 'center',
    justifyContent: 'center',
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
    maxWidth: 360,
  },
  primaryButton: {
    backgroundColor: colors.lensFlatRaised,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    height: 48,
    paddingHorizontal: spacing.xl,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  primaryButtonText: {
    ...typography.subtitle,
    color: colors.ink,
    fontSize: 14,
  },
});

