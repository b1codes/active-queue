import React from 'react';
import {
  Alert,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { colors, rounded, spacing, typography } from '../../../core/theme';
import { useQueueStore } from '../queueStore';
import { FeedItem } from '../types';

interface FeedCardProps {
  item: FeedItem;
}

export const FeedCard: React.FC<FeedCardProps> = ({ item }) => {
  const hideFeedItem = useQueueStore((state) => state.hideFeedItem);

  const handleHide = () => {
    hideFeedItem(item.content_id);
  };

  const showOptions = () => {
    Alert.alert(
      item.title,
      'Select an action for this queued content:',
      [
        {
          text: 'Hide from Queue',
          style: 'destructive',
          onPress: handleHide,
        },
        {
          text: 'Cancel',
          style: 'cancel',
        },
      ],
      { cancelable: true }
    );
  };

  return (
    <TouchableOpacity
      style={styles.card}
      onLongPress={showOptions}
      activeOpacity={0.9}
      accessible={true}
      accessibilityLabel={`${item.title}, duration ${item.duration_label}, provider ${item.provider}`}
      accessibilityHint="Double tap to view, long press to open options to hide from queue"
      accessibilityActions={[{ name: 'hide', label: 'Hide from queue' }]}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === 'hide') {
          handleHide();
        }
      }}
    >
      {item.thumbnail_url ? (
        <Image source={{ uri: item.thumbnail_url }} style={styles.thumbnail} resizeMode="cover" />
      ) : (
        <View style={[styles.thumbnail, styles.thumbnailPlaceholder]}>
          <Text style={styles.placeholderText}>{item.provider.toUpperCase()}</Text>
        </View>
      )}

      <View style={styles.content}>
        <View style={styles.badgeRow}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{item.provider.toUpperCase()}</Text>
          </View>

          <View style={styles.headerRightRow}>
            <Text style={styles.durationText}>{item.duration_label}</Text>
            <TouchableOpacity
              style={styles.moreButton}
              onPress={showOptions}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              accessibilityLabel="Content options"
            >
              <Text style={styles.moreButtonText}>⋮</Text>
            </TouchableOpacity>
          </View>
        </View>

        <Text style={styles.title} numberOfLines={2}>
          {item.title}
        </Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    flexDirection: 'row',
    marginHorizontal: spacing.lg,
    marginVertical: spacing.xs,
    overflow: 'hidden',
  },
  thumbnail: {
    height: 90,
    width: 120,
  },
  thumbnailPlaceholder: {
    alignItems: 'center',
    backgroundColor: colors.strata,
    justifyContent: 'center',
  },
  placeholderText: {
    ...typography.label,
    color: colors.inkMuted,
  },
  content: {
    flex: 1,
    justifyContent: 'space-between',
    padding: spacing.sm,
  },
  badgeRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  headerRightRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
  },
  badge: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.xs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
  badgeText: {
    color: colors.void,
    fontSize: 10,
    fontWeight: 'bold',
  },
  durationText: {
    ...typography.duration,
    color: colors.signalVerified,
  },
  moreButton: {
    paddingHorizontal: spacing.xs,
  },
  moreButtonText: {
    color: colors.inkSecondary,
    fontSize: 16,
    fontWeight: 'bold',
  },
  title: {
    ...typography.body,
    color: colors.ink,
    marginTop: spacing.xs,
  },
});
