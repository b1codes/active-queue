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
  isMatched?: boolean;
}

/**
 * Formats seconds into tabular duration string M:SS or H:MM:SS
 * Per DESIGN.md §5 Tabular Duration Rule
 */
function formatTabularDuration(seconds: number, fallbackLabel?: string): string {
  if (seconds && seconds > 0) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const mStr = hrs > 0 ? String(mins).padStart(2, '0') : String(mins);
    const sStr = String(secs).padStart(2, '0');
    return hrs > 0 ? `${hrs}:${mStr}:${sStr}` : `${mStr}:${sStr}`;
  }
  if (fallbackLabel && fallbackLabel.includes(':')) {
    return fallbackLabel.trim();
  }
  return '--:--';
}

export const FeedCard: React.FC<FeedCardProps> = memo(({ item, isMatched = false }) => {
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
  const rawProvider = (item?.provider || 'Source').trim();
  const safeProvider = rawProvider.charAt(0).toUpperCase() + rawProvider.slice(1).toLowerCase();
  const formattedDuration = formatTabularDuration(item?.duration_seconds, item?.duration_label);

  return (
    <View style={styles.cardContainer}>
      <View style={[styles.card, isMatched && styles.cardMatched]}>
        <TouchableOpacity
          style={styles.cardMainTouchable}
          onLongPress={showOptions}
          activeOpacity={0.85}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel={`${safeTitle}, duration ${formattedDuration}, from ${safeProvider}${isMatched ? ', duration matched' : ''}`}
          accessibilityHint="Double tap to view, long press for options"
        >
          {/* Thumbnail with 16:9 Aspect Ratio & Refractive Edge */}
          {item?.thumbnail_url ? (
            <View style={styles.thumbnailWrapper}>
              <Image source={{ uri: item.thumbnail_url }} style={styles.thumbnail} resizeMode="cover" />
            </View>
          ) : (
            <View style={[styles.thumbnailWrapper, styles.thumbnailPlaceholder]}>
              <Ionicons name="film-outline" size={22} color={colors.inkFaint} />
            </View>
          )}

          {/* Card Content Column */}
          <View style={styles.content}>
            <Text style={styles.title} numberOfLines={2} ellipsizeMode="tail">
              {safeTitle}
            </Text>

            <View style={styles.metaRow}>
              <Text style={styles.providerText} numberOfLines={1}>
                {safeProvider}
              </Text>

              {/* Signature Duration Pill per DESIGN.md §5 */}
              <View style={[styles.durationPill, isMatched ? styles.durationPillMatched : styles.durationPillRest]}>
                <Text style={[styles.durationText, isMatched ? styles.durationTextMatched : styles.durationTextRest]}>
                  {formattedDuration}
                </Text>
              </View>
            </View>
          </View>
        </TouchableOpacity>

        {/* Options Overflow Action Button */}
        <TouchableOpacity
          style={styles.moreButton}
          onPress={showOptions}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel={`Options for ${safeTitle}`}
          accessibilityHint="Open menu to hide from queue"
        >
          <Ionicons name="ellipsis-vertical" size={18} color={colors.inkFaint} />
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
    // One Lens Rule: lensFlat composite ground over Void
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecularLight,
    borderRadius: rounded.md,
    borderWidth: 1,
    flexDirection: 'row',
    overflow: 'hidden',
    position: 'relative',
    padding: spacing.sm,
  },
  cardMatched: {
    borderColor: 'rgba(255, 59, 48, 0.4)',
  },
  cardMainTouchable: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  thumbnailWrapper: {
    width: 104,
    height: 58.5, // 16:9 ratio
    borderRadius: rounded.xs,
    overflow: 'hidden',
    backgroundColor: colors.strata,
    borderWidth: 1,
    borderColor: colors.glassEdge,
  },
  thumbnail: {
    width: '100%',
    height: '100%',
  },
  thumbnailPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    flex: 1,
    justifyContent: 'space-between',
    paddingRight: spacing.xl,
  },
  title: {
    ...typography.subtitle,
    color: colors.ink,
    fontSize: 15,
    lineHeight: 20,
  },
  metaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.xs,
    gap: spacing.xs,
  },
  providerText: {
    ...typography.bodySm,
    color: colors.inkMuted,
    fontSize: 13,
    flex: 1,
  },
  // Signature Duration Pill per DESIGN.md §5
  durationPill: {
    height: 24,
    borderRadius: rounded.pill,
    paddingHorizontal: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  durationPillRest: {
    backgroundColor: colors.strata,
  },
  durationPillMatched: {
    backgroundColor: colors.heatCore,
  },
  durationText: {
    ...typography.duration,
    fontSize: 13,
    lineHeight: 16,
  },
  durationTextRest: {
    color: colors.ink,
  },
  // Black Label Rule: Void ink on Heat Core fill per DESIGN.md §2
  durationTextMatched: {
    color: colors.void,
    fontWeight: '700',
  },
  moreButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 44,
    position: 'absolute',
    right: spacing.xs,
    top: spacing.xs,
  },
});

