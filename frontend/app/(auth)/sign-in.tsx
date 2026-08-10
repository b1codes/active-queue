import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { colors, typography, spacing } from "@/core/theme";
import { useAuthStore } from "@/features/auth/authStore";

export default function SignInScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { signInWithEmail, signInWithEmulator, isLoading, error } = useAuthStore();

  const handleSignIn = async () => {
    if (!email || !password) return;
    try {
      await signInWithEmail(email, password);
    } catch {
      // Error handled in store
    }
  };

  const handleEmulatorSignIn = async () => {
    await signInWithEmulator();
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.content}>
        <View style={styles.headerContainer}>
          <Text style={styles.brandTitle}>ActiveQueue</Text>
          <Text style={styles.subtitle}>Time-boxed activity & media orchestrator</Text>
        </View>

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <View style={styles.form}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="user@example.com"
              placeholderTextColor={colors.inkMuted}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor={colors.inkMuted}
              secureTextEntry
            />
          </View>

          <TouchableOpacity
            style={[styles.button, isLoading && styles.buttonDisabled]}
            onPress={handleSignIn}
            disabled={isLoading}
            activeOpacity={0.8}
          >
            {isLoading ? (
              <ActivityIndicator color={colors.ink} />
            ) : (
              <Text style={styles.buttonText}>Sign In</Text>
            )}
          </TouchableOpacity>

          <View style={styles.dividerContainer}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>EMULATOR DEV MODE</Text>
            <View style={styles.dividerLine} />
          </View>

          <TouchableOpacity
            style={styles.emulatorButton}
            onPress={handleEmulatorSignIn}
            disabled={isLoading}
            activeOpacity={0.8}
          >
            <Text style={styles.emulatorButtonText}>⚡ Quick Login with Emulator User</Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.void,
  },
  content: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  headerContainer: {
    marginBottom: spacing.xxl,
    alignItems: "center",
  },
  brandTitle: {
    ...typography.display,
    color: colors.ink,
    fontSize: 36,
    fontWeight: "700",
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    textAlign: "center",
  },
  errorBanner: {
    backgroundColor: "rgba(255, 59, 48, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(255, 59, 48, 0.4)",
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  errorText: {
    ...typography.caption,
    color: colors.heatCore,
    textAlign: "center",
  },
  form: {
    gap: spacing.lg,
  },
  inputGroup: {
    gap: spacing.xs,
  },
  label: {
    ...typography.label,
    color: colors.inkSecondary,
    fontSize: 12,
  },
  input: {
    backgroundColor: colors.substrate,
    borderWidth: 1,
    borderColor: colors.glassEdge,
    borderRadius: 10,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    color: colors.ink,
    fontSize: 16,
  },
  button: {
    backgroundColor: colors.heatCore,
    borderRadius: 10,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    ...typography.body,
    color: colors.ink,
    fontWeight: "600",
    fontSize: 16,
  },
  dividerContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: spacing.md,
    gap: spacing.sm,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.glassEdge,
  },
  dividerText: {
    ...typography.caption,
    color: colors.inkMuted,
    fontSize: 10,
    fontWeight: "600",
  },
  emulatorButton: {
    backgroundColor: colors.strata,
    borderWidth: 1,
    borderColor: colors.glassEdge,
    borderRadius: 10,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  emulatorButtonText: {
    ...typography.body,
    color: colors.signalVerified,
    fontWeight: "500",
    fontSize: 14,
  },
});
