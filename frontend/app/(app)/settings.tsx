import React from 'react';
import {
  Alert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, rounded, spacing, typography } from '@/core/theme';
import { useAuthStore } from '@/features/auth/authStore';

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
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
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.headerBorder}>
        <View style={styles.header}>
          <Text style={styles.title}>Settings</Text>
        </View>
      </View>

      <View style={styles.content}>
        {/* User Account Card */}
        <View style={styles.card}>
          <Text style={styles.cardSectionTitle}>Account Profile</Text>

          <View style={styles.infoRow}>
            <Ionicons name="person-circle-outline" size={24} color={colors.heatCore} />
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
              <Text style={styles.infoLabel}>Email</Text>
              <Text style={styles.infoValue}>
                {user?.email || 'N/A'}
              </Text>
            </View>
          </View>
        </View>

        {/* Local Dev & Emulator Shortcuts */}
        <View style={styles.card}>
          <Text style={styles.cardSectionTitle}>Local Development & Testing</Text>

          <TouchableOpacity
            style={styles.emulatorButton}
            onPress={handleEmulatorSignIn}
            activeOpacity={0.8}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Re-authenticate as Emulator User"
            accessibilityHint="Double tap to sign in with seeded primary test user ID (test-user-123)"
          >
            <Ionicons name="flash-outline" size={20} color={colors.signalVerified} />
            <Text style={styles.emulatorButtonText}>
              Re-authenticate as Emulator User (test-user-123)
            </Text>
          </TouchableOpacity>
        </View>

        {/* Sign Out Action */}
        <TouchableOpacity
          style={styles.signOutButton}
          onPress={handleSignOut}
          activeOpacity={0.8}
          accessible={true}
          accessibilityRole="button"
          accessibilityLabel="Sign Out"
          accessibilityHint="Double tap to sign out of your account"
        >
          <Ionicons name="log-out-outline" size={20} color={colors.heatCore} />
          <Text style={styles.signOutButtonText}>Sign Out</Text>
        </TouchableOpacity>
      </View>
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
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.md,
  },
  cardSectionTitle: {
    ...typography.label,
    color: colors.inkMuted,
    fontSize: 12,
    letterSpacing: 0.5,
    marginBottom: spacing.md,
    textTransform: 'uppercase',
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
    backgroundColor: colors.strata,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  emulatorButtonText: {
    ...typography.body,
    color: colors.signalVerified,
    fontSize: 14,
    fontWeight: '600',
  },
  signOutButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
    borderColor: 'rgba(255, 59, 48, 0.3)',
    borderRadius: rounded.sm,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  signOutButtonText: {
    ...typography.body,
    color: colors.heatCore,
    fontSize: 15,
    fontWeight: '600',
  },
});
