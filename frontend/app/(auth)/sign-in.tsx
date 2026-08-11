import React, { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { ThermalGlowTouchable } from "@/core/components";
import { colors, rounded, spacing, typography } from "@/core/theme";
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

  const isButtonDisabled = isLoading || !email || !password;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.content}>
        {/* Brand Identity Header */}
        <View style={styles.headerContainer}>
          <Text style={styles.brandTitle} maxFontSizeMultiplier={1.5}>
            ActiveQueue
          </Text>
          <Text style={styles.subtitle} maxFontSizeMultiplier={1.5}>
            Time-boxed activity & media orchestrator
          </Text>
        </View>

        {/* Actionable Accessible Error Banner */}
        {error ? (
          <View
            style={styles.errorBanner}
            accessible={true}
            accessibilityRole="alert"
            accessibilityLiveRegion="polite"
            accessibilityLabel={`Authentication error: ${error}`}
          >
            <Ionicons name="alert-circle-outline" size={20} color={colors.ink} />
            <Text style={styles.errorText}>
              {error.includes("user-not-found") || error.includes("wrong-password") || error.includes("invalid-credential")
                ? "Invalid email address or password. Please verify your details."
                : error}
            </Text>
          </View>
        ) : null}

        {/* Credentials Form */}
        <View style={styles.form}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email address</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="name@example.com"
              placeholderTextColor={colors.inkMuted}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              accessible={true}
              accessibilityLabel="Email address"
              accessibilityHint="Enter your account email address"
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
              accessible={true}
              accessibilityLabel="Password"
              accessibilityHint="Enter your account password"
            />
          </View>

          {/* Commitment Action: Primary Button with Thermal Glow Physics */}
          <ThermalGlowTouchable
            style={[
              styles.button,
              isButtonDisabled && styles.buttonDisabled,
            ]}
            onPress={handleSignIn}
            disabled={isButtonDisabled}
            borderRadius={rounded.md}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Sign in"
            accessibilityHint="Double tap to authenticate and access your queue"
          >
            {isLoading ? (
              <ActivityIndicator color={colors.void} size="small" />
            ) : (
              <Text style={styles.buttonText}>Sign in</Text>
            )}
          </ThermalGlowTouchable>

          {/* Development Shortcut Section */}
          <View style={styles.dividerContainer}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>Development testing</Text>
            <View style={styles.dividerLine} />
          </View>

          <TouchableOpacity
            style={styles.emulatorButton}
            onPress={handleEmulatorSignIn}
            disabled={isLoading}
            activeOpacity={0.85}
            accessible={true}
            accessibilityRole="button"
            accessibilityLabel="Quick sign in as emulator user"
            accessibilityHint="Double tap to log in instantly using the local Firebase emulator"
          >
            <Ionicons name="flash-outline" size={18} color={colors.signalVerified} />
            <Text style={styles.emulatorButtonText}>Quick sign in (emulator)</Text>
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
    maxWidth: 440,
    alignSelf: "center",
    width: "100%",
    paddingHorizontal: spacing.xl,
  },
  headerContainer: {
    marginBottom: spacing.xxl,
    alignItems: "center",
  },
  brandTitle: {
    ...typography.display,
    color: colors.ink,
    fontSize: 34,
    lineHeight: 38,
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.body,
    color: colors.inkSecondary,
    textAlign: "center",
    fontSize: 15,
  },
  errorBanner: {
    backgroundColor: colors.lensFlat,
    borderWidth: 1,
    borderColor: colors.ink,
    borderRadius: rounded.sm,
    padding: spacing.md,
    marginBottom: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  errorText: {
    ...typography.bodySm,
    color: colors.ink,
    flex: 1,
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
    fontSize: 13,
  },
  input: {
    backgroundColor: colors.lensFlat,
    borderWidth: 1,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    height: 52,
    paddingHorizontal: spacing.lg,
    color: colors.ink,
    ...typography.body,
  },
  // Primary Button: Heat Core fill with Void text (Black Label Rule per DESIGN.md §2)
  button: {
    backgroundColor: colors.heatCore,
    borderRadius: rounded.md,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
  },
  buttonDisabled: {
    backgroundColor: colors.strata,
    opacity: 0.7,
  },
  buttonText: {
    ...typography.subtitle,
    color: colors.void, // Black Label Rule: Void text on Heat Core fill
    fontWeight: "700",
  },
  dividerContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: spacing.sm,
    gap: spacing.sm,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.glassEdge,
  },
  dividerText: {
    ...typography.label,
    color: colors.inkMuted,
    fontSize: 12,
  },
  emulatorButton: {
    backgroundColor: colors.lensFlatRaised,
    borderWidth: 1,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    height: 52,
    flexDirection: "row",
    gap: spacing.xs,
    alignItems: "center",
    justifyContent: "center",
  },
  emulatorButtonText: {
    ...typography.subtitle,
    color: colors.signalVerified,
    fontSize: 15,
  },
});

