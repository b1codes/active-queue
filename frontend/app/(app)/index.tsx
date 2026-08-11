import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  AppState,
  FlatList,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import {
  ActiveSessionBanner,
  EmptyFeedState,
  NoSourcesState,
  OfflineBanner,
  ProviderQuotaBanner,
  SyncResumableCard,
} from '@/core/components/states';
import { GlassHeader, QueueSkeletonList } from '@/core/components';

import { colors, rounded, spacing, typography } from '@/core/theme';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '@/features/auth/authStore';
import { AddSourceModal } from '@/features/queue/components/AddSourceModal';
import { FeedCard } from '@/features/queue/components/FeedCard';
import { SyncProgressBar } from '@/features/queue/components/SyncProgressBar';
import { useQueueStore } from '@/features/queue/queueStore';
import { useSessionStore } from '@/features/sessions/sessionStore';

export default function QueueScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signOut } = useAuthStore();

  const feedItems = useQueueStore((state) => state.feedItems);
  const totalUnconsumed = useQueueStore((state) => state.totalUnconsumed);
  const isLoadingFeed = useQueueStore((state) => state.isLoadingFeed);
  const isRefreshingFeed = useQueueStore((state) => state.isRefreshingFeed);
  const fetchFeed = useQueueStore((state) => state.fetchFeed);
  const startResumableSync = useQueueStore((state) => state.startResumableSync);

  const currentSession = useSessionStore((state) => state.currentSession);
  const checkActiveSession = useSessionStore((state) => state.checkActiveSession);

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

  const handleResumeSession = useCallback((sessionId: string) => {
    router.push({
      pathname: '/(app)/session/[id]',
      params: { id: sessionId },
    });
  }, [router]);

  const renderFeedCard = useCallback(({ item }: { item: any }) => (
    <FeedCard item={item} />
  ), []);


  const formatCount = useCallback((count: number | null): string => {
    if (count === null || count === undefined) return '';
    if (count > 999) return `${(count / 1000).toFixed(1)}k`;
    return `${count}`;
  }, []);

  const getItemLayout = useCallback(
    (_: any, index: number) => ({
      length: 88,
      offset: 88 * index,
      index,
    }),
    []
  );

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <GlassHeader
        title="Active Queue"
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
        <QueueSkeletonList count={4} />
      ) : feedItems.length === 0 ? (
        <NoSourcesState onAddSourcePress={() => setIsAddModalVisible(true)} />
      ) : (
        <FlatList
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
          getItemLayout={getItemLayout}
          removeClippedSubviews={Platform.OS === 'android'}
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
    paddingVertical: spacing.sm,
  },
  loadingContainer: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
});
