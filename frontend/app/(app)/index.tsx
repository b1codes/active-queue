import React, { useCallback, useEffect, useState } from 'react';
import {
  AppState,
  FlatList,
  Platform,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from '@/core/components/Text';
import { useRouter } from 'expo-router';
import {
  ActiveSessionBanner,
  EmptyFeedState,
  NoSourcesState,
  OfflineBanner,
  ProviderQuotaBanner,
  SyncResumableCard,
} from '@/core/components/states';
import { GlassHeader, QueueSkeletonList, useGlassHeaderHeight } from '@/core/components';

import { colors, rounded, spacing, typography } from '@/core/theme';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '@/features/auth/authStore';
import { AddSourceModal } from '@/features/queue/components/AddSourceModal';
import { FeedCard } from '@/features/queue/components/FeedCard';
import { SyncProgressBar } from '@/features/queue/components/SyncProgressBar';
import { useQueueStore } from '@/features/queue/queueStore';
import type { FeedItem } from '@/features/queue/types';
import { NETWORK_UNAVAILABLE } from '@/core/api/apiClient';
import { useSessionStore } from '@/features/sessions/sessionStore';

export default function QueueScreen() {
  const router = useRouter();
  const [headerHeight, setHeaderHeight] = useGlassHeaderHeight();
  const { signOut } = useAuthStore();

  const feedItems = useQueueStore((state) => state.feedItems);
  const totalUnconsumed = useQueueStore((state) => state.totalUnconsumed);
  const isLoadingFeed = useQueueStore((state) => state.isLoadingFeed);
  const isRefreshingFeed = useQueueStore((state) => state.isRefreshingFeed);
  const fetchFeed = useQueueStore((state) => state.fetchFeed);
  const fetchSources = useQueueStore((state) => state.fetchSources);
  const startResumableSync = useQueueStore((state) => state.startResumableSync);
  const sources = useQueueStore((state) => state.sources);
  const feedError = useQueueStore((state) => state.feedError);
  const syncProgress = useQueueStore((state) => state.syncProgress);

  const currentSession = useSessionStore((state) => state.currentSession);
  const checkActiveSession = useSessionStore((state) => state.checkActiveSession);

  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [lastForegroundCheck, setLastForegroundCheck] = useState<number>(Date.now());
  const [dismissedResumeId, setDismissedResumeId] = useState<string | null>(null);

  // SPEC §11.3 states, all derived from store data rather than local flags.
  const isOffline = feedError?.code === NETWORK_UNAVAILABLE;
  const isQuotaExceeded =
    syncProgress.errorCode === 'PROVIDER_QUOTA_EXCEEDED' ||
    (sources ?? []).some((src) => src.status === 'quota_paused');
  // A source left mid-walk by an earlier app run. Never auto-resumed (needs a tap).
  const resumableSource = syncProgress.isSyncing
    ? null
    : (sources ?? []).find((src) => src.status === 'syncing' && src.id !== dismissedResumeId) ??
      null;

  const handleInitialFetch = useCallback(async () => {
    await Promise.all([fetchFeed(true), fetchSources(), checkActiveSession()]);
  }, [fetchFeed, fetchSources, checkActiveSession]);

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

  const handleResumeSession = useCallback((sessionId: string) => {
    router.push({
      pathname: '/(app)/session/[id]',
      params: { id: sessionId },
    });
  }, [router]);

  const openMatch = useCallback(
    (item: FeedItem) => {
      router.push({ pathname: '/(app)/match/[contentId]', params: { contentId: item.content_id } });
    },
    [router]
  );

  const renderFeedCard = useCallback(
    ({ item }: { item: FeedItem }) => <FeedCard item={item} onPress={openMatch} />,
    [openMatch]
  );


  const formatCount = useCallback((count: number | null): string => {
    if (count === null || count === undefined) return '';
    if (count > 999) return `${(count / 1000).toFixed(1)}k`;
    return `${count}`;
  }, []);

  // Banner stack rides inside the scroll content rather than sitting between the header and
  // the list: the header is an overlay now, so anything in flow above the list would be hidden
  // underneath it, and the list has to reach the top of the screen for content to pass behind
  // the glass at all.
  const bannerStack = (
    <>
      {/* Top Banner Notifications per SPEC §11.3 */}
      {isOffline ? <OfflineBanner onRetryPress={handleInitialFetch} /> : null}

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
          onFinishSyncPress={() => startResumableSync(resumableSource.id, resumableSource.item_count)}
          onDismissPress={() => setDismissedResumeId(resumableSource.id)}
        />
      ) : null}
    </>
  );

  return (
    <View style={styles.container}>
      {/* Main Feed Content or Designed Empty States */}
      {feedItems.length === 0 && isLoadingFeed ? (
        <View style={[styles.staticContent, { paddingTop: headerHeight }]}>
          {bannerStack}
          <QueueSkeletonList count={4} />
        </View>
      ) : feedItems.length === 0 ? (
        <View style={[styles.staticContent, { paddingTop: headerHeight }]}>
          {bannerStack}
          {sources !== null && sources.length === 0 ? (
            <NoSourcesState onAddSourcePress={() => setIsAddModalVisible(true)} />
          ) : sources !== null ? (
            // Sources exist but nothing is queued: "all caught up", not "add a source".
            <EmptyFeedState
              onSyncPress={() => sources[0] && startResumableSync(sources[0].id, sources[0].item_count)}
              onAddSourcePress={() => setIsAddModalVisible(true)}
            />
          ) : null}
        </View>
      ) : (
        <FlatList
          testID="queue-list"
          data={feedItems}
          keyExtractor={(item) => item.id || item.content_id}
          renderItem={renderFeedCard}
          refreshing={isRefreshingFeed}
          onRefresh={() => fetchFeed(true)}
          onEndReached={() => fetchFeed(false)}
          onEndReachedThreshold={0.5}
          initialNumToRender={8}
          maxToRenderPerBatch={10}
          windowSize={5}
          removeClippedSubviews={Platform.OS === 'android'}
          ListHeaderComponent={bannerStack}
          contentContainerStyle={[styles.listContent, { paddingTop: headerHeight }]}
          scrollIndicatorInsets={{ top: headerHeight }}
          ListEmptyComponent={
            <EmptyFeedState
              onSyncPress={() => fetchFeed(true)}
              onAddSourcePress={() => setIsAddModalVisible(true)}
            />
          }
        />
      )}

      <GlassHeader
        title="Active Queue"
        onHeightChange={setHeaderHeight}
        leftComponent={
          totalUnconsumed !== null ? (
            <View style={styles.countBadge}>
              <Text style={styles.countBadgeText}>{formatCount(totalUnconsumed)}</Text>
            </View>
          ) : undefined
        }
        rightComponent={
          <>
            <TouchableOpacity
              style={styles.addButton}
              onPress={() => setIsAddModalVisible(true)}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Add Source"
              accessibilityHint="Open modal to add a new YouTube playlist URL or custom source"
            >
              <Text style={styles.addButtonText}>+ Add Source</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.iconButton}
              onPress={() => signOut()}
              accessible={true}
              accessibilityRole="button"
              accessibilityLabel="Sign Out"
              accessibilityHint="Sign out of current account"
            >
              <Ionicons name="log-out-outline" size={20} color={colors.inkSecondary} />
            </TouchableOpacity>
          </>
        }
      />

      <AddSourceModal
        visible={isAddModalVisible}
        onClose={() => setIsAddModalVisible(false)}
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
    alignItems: 'center',
    alignSelf: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    width: '100%',
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
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
  },
  addButton: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  iconButton: {
    alignItems: 'center',
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 44,
  },
  addButtonText: {
    ...typography.label,
    color: colors.ink,
  },
  listContent: {
    paddingBottom: spacing.sm,
  },
  staticContent: {
    flex: 1,
  },
  loadingContainer: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
});
