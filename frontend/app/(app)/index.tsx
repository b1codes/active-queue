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
import { useRouter } from 'expo-router';
import {
  ActiveSessionBanner,
  EmptyFeedState,
  NoSourcesState,
  OfflineBanner,
  ProviderQuotaBanner,
  SyncResumableCard,
} from '../../src/core/components/states';
import { colors, rounded, spacing, typography } from '../../src/core/theme';
import { AddSourceModal } from '../../src/features/queue/components/AddSourceModal';
import { FeedCard } from '../../src/features/queue/components/FeedCard';
import { SyncProgressBar } from '../../src/features/queue/components/SyncProgressBar';
import { useQueueStore } from '../../src/features/queue/queueStore';
import { useSessionStore } from '../../src/features/sessions/sessionStore';

export default function QueueScreen() {
  const router = useRouter();
  const {
    feedItems,
    totalUnconsumed,
    isLoadingFeed,
    isRefreshingFeed,
    fetchFeed,
    startResumableSync,
  } = useQueueStore();

  const { currentSession, checkActiveSession } = useSessionStore();

  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [lastForegroundCheck, setLastForegroundCheck] = useState<number>(Date.now());
  const [isOffline, setIsOffline] = useState(false);
  const [isQuotaExceeded] = useState(false);
  const [resumableSource, setResumableSource] = useState<{ id: string; title: string } | null>(null);

  const handleInitialFetch = useCallback(async () => {
    try {
      await fetchFeed(true);
      await checkActiveSession();
    } catch {
      setIsOffline(true);
    }
  }, [fetchFeed, checkActiveSession]);

  useEffect(() => {
    handleInitialFetch();
  }, [handleInitialFetch]);

  // Foreground listener with 6-hour auto-sync guardrail per SPEC §9.4
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState) => {
      if (nextAppState === 'active') {
        const now = Date.now();
        const SIX_HOURS_MS = 6 * 60 * 60 * 1000;
        if (now - lastForegroundCheck > SIX_HOURS_MS) {
          setLastForegroundCheck(now);
          fetchFeed(true);
          checkActiveSession();
        }
      }
    });

    return () => {
      subscription.remove();
    };
  }, [lastForegroundCheck, fetchFeed, checkActiveSession]);

  const handleResumeSession = (sessionId: string) => {
    router.push({
      pathname: '/(app)/session/[id]',
      params: { id: sessionId },
    });
  };

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

      {/* Top Banner Notifications per SPEC §11.3 */}
      {isOffline ? (
        <OfflineBanner onRetryPress={() => { setIsOffline(false); fetchFeed(true); }} />
      ) : null}

      {isQuotaExceeded ? <ProviderQuotaBanner /> : null}

      {currentSession ? (
        <ActiveSessionBanner
          sessionId={currentSession.id}
          activityId={currentSession.activity_id}
          durationSeconds={currentSession.duration_seconds}
          onResumePress={handleResumeSession}
        />
      ) : null}

      <SyncProgressBar />

      {resumableSource ? (
        <SyncResumableCard
          sourceTitle={resumableSource.title}
          onFinishSyncPress={() => {
            startResumableSync(resumableSource.id);
            setResumableSource(null);
          }}
          onDismissPress={() => setResumableSource(null)}
        />
      ) : null}

      {/* Main Feed Content or Designed Empty States */}
      {feedItems.length === 0 && isLoadingFeed ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator color={colors.heatCore} size="large" />
        </View>
      ) : feedItems.length === 0 ? (
        <NoSourcesState onAddSourcePress={() => setIsAddModalVisible(true)} />
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
          ListEmptyComponent={
            <EmptyFeedState
              onSyncPress={() => fetchFeed(true)}
              onAddSourcePress={() => setIsAddModalVisible(true)}
            />
          }
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
});
