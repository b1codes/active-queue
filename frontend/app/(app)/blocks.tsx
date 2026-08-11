import React, { useState } from 'react';
import {
  ScrollView,
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
import { useQueueStore } from '@/features/queue/queueStore';

interface DurationOption {
  label: string;
  seconds: number;
}

const DURATION_PRESETS: DurationOption[] = [
  { label: '15:00', seconds: 900 },
  { label: '20:00', seconds: 1200 },
  { label: '30:00', seconds: 1800 },
  { label: '45:00', seconds: 2700 },
  { label: '60:00', seconds: 3600 },
  { label: '90:00', seconds: 5400 },
];

const ACTIVITIES = [
  { id: 'zone2', name: 'Zone 2 Cardio', icon: 'heart-outline' },
  { id: 'treadmill', name: 'Treadmill Run', icon: 'walk-outline' },
  { id: 'cycling', name: 'Indoor Cycling', icon: 'bicycle-outline' },
  { id: 'rowing', name: 'Rowing', icon: 'boat-outline' },
  { id: 'strength', name: 'Strength Training', icon: 'barbell-outline' },
];

export default function BlocksScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const feedItems = useQueueStore((state) => state.feedItems);

  const [selectedDuration, setSelectedDuration] = useState<number>(1800); // 30 mins default
  const [selectedActivity, setSelectedActivity] = useState<string>('zone2');

  // Find exact or closest media item match in the queue
  const matchedItem = feedItems.find(
    (item) => Math.abs(item.duration_seconds - selectedDuration) <= 300
  ) || feedItems[0];

  const formattedSelectedLabel = DURATION_PRESETS.find(
    (d) => d.seconds === selectedDuration
  )?.label || `${Math.floor(selectedDuration / 60)}:00`;

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <GlassHeader
        title="Time Blocks"
        subtitle="Time-first activity & runtime orchestrator"
      />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Section 1: Workout Duration Selector */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Select Workout Duration</Text>
          <View style={styles.presetGrid}>
            {DURATION_PRESETS.map((preset) => {
              const isSelected = selectedDuration === preset.seconds;
              return (
                <TouchableOpacity
                  key={preset.seconds}
                  style={[
                    styles.durationButton,
                    isSelected ? styles.durationButtonSelected : styles.durationButtonUnselected,
                  ]}
                  onPress={() => setSelectedDuration(preset.seconds)}
                  activeOpacity={0.85}
                  accessible={true}
                  accessibilityRole="button"
                  accessibilityLabel={`Target duration ${preset.label}`}
                  accessibilityState={{ selected: isSelected }}
                >
                  <Text
                    style={[
                      styles.durationButtonText,
                      isSelected ? styles.durationButtonTextSelected : styles.durationButtonTextUnselected,
                    ]}
                  >
                    {preset.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* Section 2: Activity Selector Chips */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Activity Type</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            {ACTIVITIES.map((act) => {
              const isSelected = selectedActivity === act.id;
              return (
                <TouchableOpacity
                  key={act.id}
                  style={[
                    styles.chip,
                    isSelected ? styles.chipSelected : styles.chipUnselected,
                  ]}
                  onPress={() => setSelectedActivity(act.id)}
                  activeOpacity={0.85}
                  accessible={true}
                  accessibilityRole="button"
                  accessibilityLabel={`Activity ${act.name}`}
                  accessibilityState={{ selected: isSelected }}
                >
                  <Ionicons
                    name={act.icon as any}
                    size={16}
                    color={isSelected ? colors.void : colors.inkSecondary}
                  />
                  <Text style={[styles.chipText, isSelected ? styles.chipTextSelected : styles.chipTextUnselected]}>
                    {act.name}
                  </Text>
                  {isSelected ? <Ionicons name="checkmark" size={14} color={colors.void} /> : null}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Section 3: Matched Media Card or Designed Empty State */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Matched Media</Text>

          {matchedItem ? (
            <View style={styles.matchCard}>
              <View style={styles.matchHeader}>
                <View style={styles.matchBadge}>
                  <Ionicons name="sparkles" size={14} color={colors.heatCore} />
                  <Text style={styles.matchBadgeText}>Target Match ({formattedSelectedLabel})</Text>
                </View>

                {/* Signature Duration Pill in Heat Core fill per DESIGN.md §5 */}
                <View style={styles.durationPillMatched}>
                  <Text style={styles.durationTextMatched}>
                    {matchedItem.duration_label}
                  </Text>
                </View>
              </View>

              <Text style={styles.itemTitle} numberOfLines={2}>
                {matchedItem.title}
              </Text>
              <Text style={styles.itemMeta}>
                Provider: {matchedItem.provider.toUpperCase()}
              </Text>

              {/* Commitment Action: Primary Button per Black Label Rule */}
              <TouchableOpacity
                style={styles.startButton}
                onPress={() => router.push(`/(app)/match/${matchedItem.content_id}`)}
                activeOpacity={0.85}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Start session with matched media"
              >
                <Text style={styles.startButtonText}>Start Session ({formattedSelectedLabel})</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.emptyCard}>
              <Ionicons name="layers-outline" size={32} color={colors.inkFaint} />
              <Text style={styles.emptyTitle}>No Queued Media Available</Text>
              <Text style={styles.emptyBody}>
                Add your favorite YouTube playlists or video sources to start matching workout time blocks.
              </Text>
              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={() => router.push('/(app)')}
                activeOpacity={0.85}
                accessible={true}
                accessibilityRole="button"
                accessibilityLabel="Go to Queue to add sources"
              >
                <Text style={styles.secondaryButtonText}>Return to Queue</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>
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
    height: 48,
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
    color: colors.heatCore,
    fontWeight: '700',
  },
  chipRow: {
    gap: spacing.xs,
  },
  chip: {
    height: 36,
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
    height: 24,
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

