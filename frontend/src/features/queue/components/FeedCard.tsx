import React, { memo } from 'react';
import {
  Alert,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, rounded, spacing, typography } from '../../../core/theme';
import { useQueueStore } from '../queueStore';
import { FeedItem } from '../types';

interface FeedCardProps {
  item: FeedItem;
}

export const FeedCard: React.FC<FeedCardProps> = memo(({ item }) => {
  const hideFeedItem = useQueueStore((state) => state.hideFeedItem);

  const handleHide = () => {
    if (item?.content_id) {
      hideFeedItem(item.content_id);
    }
  };

  const showOptions = () => {
    Alert.alert(
      item?.title || 'Queued Content',
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

  const safeTitle = (item?.title || 'Untitled Content').trim();
  const safeProvider = (item?.provider || 'Unknown').toUpperCase().trim();
  const safeDuration = item?.duration_label || '--:--';

  return (
    <View style={styles.cardContainer}>
      <View style={styles.card}>
        <TouchableOpacity
          style={styles.cardMainTouchable}
          onLongPress={showOptions}
          activeOpacity={0.9}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel={`${safeTitle}, duration ${safeDuration}, provider ${safeProvider}`}
          accessibilityHint="Double tap to view, long press for options"
        >
          {item?.thumbnail_url ? (
            <Image source={{ uri: item.thumbnail_url }} style={styles.thumbnail} resizeMode="cover" />
          ) : (
            <View style={[styles.thumbnail, styles.thumbnailPlaceholder]}>
              <Text style={styles.placeholderText} numberOfLines={1}>{safeProvider}</Text>
            </View>
          )}

          <View style={styles.content}>
            <View style={styles.badgeRow}>
              <View style={styles.badge}>
                <Text style={styles.badgeText} numberOfLines={1} ellipsizeMode="tail">{safeProvider}</Text>
              </View>

              <Text style={styles.durationText}>{safeDuration}</Text>
            </View>

            <Text style={styles.title} numberOfLines={2} ellipsizeMode="tail">
              {safeTitle}
            </Text>
          </View>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.moreButton}
          onPress={showOptions}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel={`Options for ${safeTitle}`}
          accessibilityHint="Open menu to hide from queue"
        >
          <Ionicons name="ellipsis-vertical" size={18} color={colors.inkSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
});

FeedCard.displayName = 'FeedCard';

const styles = StyleSheet.create({
  cardContainer: {
    alignSelf: 'center',
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
    width: '100%',
  },
  card: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    flexDirection: 'row',
    overflow: 'hidden',
    position: 'relative',
  },
  cardMainTouchable: {
    flex: 1,
    flexDirection: 'row',
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
    paddingRight: 48,
  },
  badgeRow: {
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
    ...typography.badge,
    color: colors.void,
  },
  durationText: {
    ...typography.duration,
    color: colors.signalVerified,
  },
  moreButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 44,
    position: 'absolute',
    right: 4,
    top: 4,
  },
  title: {
    ...typography.body,
    color: colors.ink,
    marginTop: spacing.xs,
  },
});
