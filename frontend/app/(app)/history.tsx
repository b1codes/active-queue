import React from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { GlassHeader } from '@/core/components';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { useRouter } from 'expo-router';
import { useSessionStore } from '@/features/sessions/sessionStore';

export default function HistoryScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  // Retrieve past session logs or empty array
  const activeSession = useSessionStore((state) => state.currentSession);
  const historySessions = activeSession ? [activeSession] : [];

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <GlassHeader
        title="History"
        subtitle="Completed workout & media sessions"
      />

      <FlatList
        data={historySessions}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <View style={styles.sessionCard}>
            <View style={styles.cardHeader}>
              <View style={styles.verifiedBadge}>
                <Ionicons name="checkmark-circle" size={18} color={colors.signalVerified} />
                <Text style={styles.verifiedText}>Session Verified</Text>
              </View>

              <View style={styles.durationPill}>
                <Text style={styles.durationText}>{formatDuration(item.duration_seconds)}</Text>
              </View>
            </View>

            <Text style={styles.cardTitle}>Activity Session #{item.id.slice(-6)}</Text>
            <Text style={styles.cardMeta}>
              Activity ID: {item.activity_id} · State: {item.status.toUpperCase()}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <View style={styles.iconCircle}>
              <Ionicons name="stats-chart-outline" size={32} color={colors.inkFaint} />
            </View>
            <Text style={styles.emptyTitle}>No Completed Sessions Yet</Text>
            <Text style={styles.emptyBody}>
              Your workout sessions matched with queued media will be logged here with HealthKit verification.
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
        }
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
    height: 24,
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

