import React from 'react';
import {
  Alert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GlassHeader, useGlassHeaderHeight } from '@/core/components';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { useAuthStore } from '@/features/auth/authStore';

export default function SettingsScreen() {
  const [headerHeight, setHeaderHeight] = useGlassHeaderHeight();
  const { user, signOut, signInWithEmulator } = useAuthStore();

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch {
      Alert.alert('Error', 'Failed to sign out. Please try again.');
    }
  };

  const handleEmulatorSignIn = async () => {
    try {
      await signInWithEmulator();
      Alert.alert('Success', 'Re-authenticated as primary test user (test-user-123)!');
    } catch {
      Alert.alert('Error', 'Failed to re-authenticate with emulator.');
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.content, { paddingTop: headerHeight + spacing.lg }]}>
        {/* User Account Card */}
        <View style={styles.card}>
          <Text style={styles.cardSectionTitle}>Account profile</Text>

          <View style={styles.infoRow}>
            <Ionicons name="person-circle-outline" size={24} color={colors.ink} />
            <View style={styles.infoTextContainer}>
              <Text style={styles.infoLabel}>User ID (UID)</Text>
              <Text style={styles.infoValue} numberOfLines={1}>
                {user?.uid || 'Not signed in'}
              </Text>
            </View>
          </View>

          <View style={styles.divider} />

          <View style={styles.infoRow}>
            <Ionicons name="mail-outline" size={22} color={colors.inkSecondary} />
            <View style={styles.infoTextContainer}>
              <Text style={styles.infoLabel}>Email address</Text>
              <Text style={styles.infoValue}>
                {user?.email || 'N/A'}
              </Text>
            </View>
          </View>
        </View>

        {/* Local Dev & Emulator Shortcuts */}
        <View style={styles.card}>
          <Text style={styles.cardSectionTitle}>Local development & testing</Text>

          <TouchableOpacity
            style={styles.emulatorButton}
            onPress={handleEmulatorSignIn}
            activeOpacity={0.85}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Re-authenticate as Emulator User"
            accessibilityHint="Double tap to sign in with primary test user ID (test-user-123)"
          >
            <Ionicons name="flash-outline" size={18} color={colors.signalVerified} />
            <Text style={styles.emulatorButtonText}>
              Re-authenticate as emulator user (test-user-123)
            </Text>
          </TouchableOpacity>
        </View>

        {/* Sign Out Action */}
        <TouchableOpacity
          style={styles.signOutButton}
          onPress={handleSignOut}
          activeOpacity={0.85}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel="Sign out"
          accessibilityHint="Double tap to sign out of your account"
        >
          <Ionicons name="log-out-outline" size={18} color={colors.inkSecondary} />
          <Text style={styles.signOutButtonText}>Sign out</Text>
        </TouchableOpacity>
      </View>

      <GlassHeader
        title="Settings"
        onHeightChange={setHeaderHeight}
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
  content: {
    alignSelf: 'center',
    gap: spacing.lg,
    maxWidth: 680,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    width: '100%',
  },
  card: {
    backgroundColor: colors.lensFlat,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecularLight,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.lg,
  },
  // Sentence Case Rule per DESIGN.md §3
  cardSectionTitle: {
    ...typography.subtitle,
    color: colors.ink,
    fontSize: 16,
    marginBottom: spacing.md,
  },
  infoRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.md,
  },
  infoTextContainer: {
    flex: 1,
  },
  infoLabel: {
    ...typography.caption,
    color: colors.inkMuted,
  },
  infoValue: {
    ...typography.body,
    color: colors.ink,
    fontWeight: '600',
    marginTop: 2,
  },
  divider: {
    backgroundColor: colors.glassEdge,
    height: 1,
    marginVertical: spacing.md,
  },
  emulatorButton: {
    alignItems: 'center',
    backgroundColor: colors.lensFlatRaised,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'center',
    height: 52,
    paddingHorizontal: spacing.md,
  },
  emulatorButtonText: {
    ...typography.subtitle,
    color: colors.signalVerified,
    fontSize: 14,
  },
  signOutButton: {
    alignItems: 'center',
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'center',
    height: 52,
    paddingHorizontal: spacing.md,
  },
  signOutButtonText: {
    ...typography.subtitle,
    color: colors.inkSecondary,
    fontSize: 15,
  },
});

