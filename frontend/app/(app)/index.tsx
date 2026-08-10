import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  AppState,
  FlatList,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { colors, rounded, spacing, typography } from '../../src/core/theme';
import { AddSourceModal } from '../../src/features/queue/components/AddSourceModal';
import { FeedCard } from '../../src/features/queue/components/FeedCard';
import { SyncProgressBar } from '../../src/features/queue/components/SyncProgressBar';
import { useQueueStore } from '../../src/features/queue/queueStore';

export default function QueueScreen() {
  const {
    feedItems,
    totalUnconsumed,
    isLoadingFeed,
    isRefreshingFeed,
    fetchFeed,
  } = useQueueStore();

  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [lastForegroundCheck, setLastForegroundCheck] = useState<number>(Date.now());

  const handleInitialFetch = useCallback(() => {
    fetchFeed(true);
  }, [fetchFeed]);

  useEffect(() => {
    handleInitialFetch();
  }, [handleInitialFetch]);

  // Foreground listener with 6-hour auto-sync guardrail per SPEC §9.4 / Subtask 8
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState) => {
      if (nextAppState === 'active') {
        const now = Date.now();
        const SIX_HOURS_MS = 6 * 60 * 60 * 1000;
        if (now - lastForegroundCheck > SIX_HOURS_MS) {
          setLastForegroundCheck(now);
          fetchFeed(true);
        }
      }
    });

    return () => {
      subscription.remove();
    };
  }, [lastForegroundCheck, fetchFeed]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>Active Queue</Text>
          {totalUnconsumed !== null ? (
            <View style={styles.countBadge}>
              <Text style={styles.countBadgeText}>{totalUnconsumed}</Text>
            </View>
          ) : null}
        </View>

        <View style={styles.headerRight}>
          <TouchableOpacity
            style={styles.addButton}
            onPress={() => setIsAddModalVisible(true)}
          >
            <Text style={styles.addButtonText}>+ Add Source</Text>
          </TouchableOpacity>
        </View>
      </View>

      <SyncProgressBar />

      {feedItems.length === 0 && isLoadingFeed ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator color={colors.heatCore} size="large" />
        </View>
      ) : feedItems.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyTitle}>Your queue is empty</Text>
          <Text style={styles.emptySubtitle}>
            Add a YouTube playlist URL to start building your workout queue.
          </Text>
          <TouchableOpacity
            style={styles.emptyAddButton}
            onPress={() => setIsAddModalVisible(true)}
          >
            <Text style={styles.emptyAddButtonText}>+ Add First Source</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={feedItems}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <FeedCard item={item} />}
          refreshing={isRefreshingFeed}
          onRefresh={() => fetchFeed(true)}
          onEndReached={() => fetchFeed(false)}
          onEndReachedThreshold={0.5}
          contentContainerStyle={styles.listContent}
        />
      )}

      <AddSourceModal
        visible={isAddModalVisible}
        onClose={() => setIsAddModalVisible(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.void,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    borderBottomColor: colors.glassEdge,
    borderBottomWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  headerLeft: {
    alignItems: 'center',
    flexDirection: 'row',
  },
  headerTitle: {
    ...typography.title,
    color: colors.ink,
  },
  countBadge: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.pill,
    marginLeft: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  countBadgeText: {
    color: colors.void,
    fontSize: 12,
    fontWeight: 'bold',
  },
  headerRight: {
    flexDirection: 'row',
  },
  addButton: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  addButtonText: {
    ...typography.label,
    color: colors.ink,
  },
  listContent: {
    paddingVertical: spacing.sm,
  },
  loadingContainer: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
  },
  emptyTitle: {
    ...typography.title,
    color: colors.ink,
    marginBottom: spacing.xs,
  },
  emptySubtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  emptyAddButton: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  emptyAddButtonText: {
    ...typography.label,
    color: colors.void,
    fontWeight: 'bold',
  },
});
