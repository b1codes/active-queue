import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { colors, rounded, spacing, typography } from '../../../core/theme';
import { FeedItem } from '../types';

interface FeedCardProps {
  item: FeedItem;
}

export const FeedCard: React.FC<FeedCardProps> = ({ item }) => {
  return (
    <View style={styles.card}>
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
          <Text style={styles.durationText}>{item.duration_label}</Text>
        </View>

        <Text style={styles.title} numberOfLines={2}>
          {item.title}
        </Text>
      </View>
    </View>
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
  title: {
    ...typography.body,
    color: colors.ink,
    marginTop: spacing.xs,
  },
});
