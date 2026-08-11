import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { WatchLaterRejectedState } from '../../../core/components/states';
import { colors, rounded, spacing, typography } from '../../../core/theme';
import { useQueueStore } from '../queueStore';

interface AddSourceModalProps {
  visible: boolean;
  onClose: () => void;
}

export const AddSourceModal: React.FC<AddSourceModalProps> = ({ visible, onClose }) => {
  const [urlOrId, setUrlOrId] = useState('');
  const { addSource, isAddingSource, addSourceError, clearErrors } = useQueueStore();

  const isWatchLaterError =
    addSourceError &&
    (addSourceError.includes('Watch Later') ||
      addSourceError.includes('SOURCE_UNSUPPORTED') ||
      addSourceError.includes('system playlist'));

  const handleAdd = async () => {
    if (!urlOrId.trim()) {
      return;
    }
    const result = await addSource(urlOrId.trim());
    if (result) {
      setUrlOrId('');
      onClose();
    }
  };

  const handleClose = () => {
    clearErrors();
    setUrlOrId('');
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={handleClose}>
      <BlurView
        intensity={30}
        tint="dark"
        experimentalBlurMethod="dimezisBlurView"
        style={styles.overlayBlur}
      >
        <KeyboardAvoidingView
          style={styles.overlay}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalContent}>
            {isWatchLaterError ? (
              <WatchLaterRejectedState
                onDismissPress={() => {
                  clearErrors();
                  setUrlOrId('');
                }}
              />
            ) : (
              <>
                <Text style={styles.title}>Add Content Source</Text>
                <Text style={styles.description}>
                  Paste a YouTube playlist URL (e.g. youtube.com/playlist?list=PL...) or raw playlist ID.
                </Text>

                <TextInput
                  style={styles.input}
                  placeholder="https://www.youtube.com/playlist?list=..."
                  placeholderTextColor={colors.inkMuted}
                  value={urlOrId}
                  onChangeText={(txt) => {
                    clearErrors();
                    setUrlOrId(txt);
                  }}
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                {addSourceError ? <Text style={styles.errorText}>{addSourceError}</Text> : null}

                <View style={styles.buttonRow}>
                  <TouchableOpacity
                    onPress={handleClose}
                    style={[styles.button, styles.cancelButton]}
                    disabled={isAddingSource}
                    accessible={true}
                    accessibilityRole="button"
                    accessibilityLabel="Cancel adding content source"
                  >
                    <Text style={styles.cancelText}>Cancel</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    onPress={handleAdd}
                    style={[styles.button, styles.submitButton]}
                    disabled={isAddingSource || !urlOrId.trim()}
                    accessible={true}
                    accessibilityRole="button"
                    accessibilityLabel="Add source"
                  >
                    {isAddingSource ? (
                      <ActivityIndicator color={colors.void} size="small" />
                    ) : (
                      <Text style={styles.submitText}>Add Source</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </BlurView>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlayBlur: {
    flex: 1,
  },
  overlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(12, 9, 9, 0.70)',
    flex: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  modalContent: {
    backgroundColor: colors.lensFlatRaised,
    borderColor: colors.glassEdge,
    borderTopColor: colors.glassSpecularLight,
    borderRadius: rounded.lg, // 20pt for L3 Raised Lens Sheet per DESIGN.md §5
    borderWidth: 1,
    maxWidth: 520,
    padding: spacing.xl,
    width: '100%',
  },
  title: {
    ...typography.title,
    color: colors.ink,
    marginBottom: spacing.xs,
  },
  description: {
    ...typography.bodySm,
    color: colors.inkSecondary,
    marginBottom: spacing.md,
  },
  input: {
    ...typography.body,
    backgroundColor: colors.void,
    borderColor: colors.glassEdge,
    borderRadius: rounded.sm,
    borderWidth: 1,
    color: colors.ink,
    minHeight: 48,
    padding: spacing.md,
  },
  errorText: {
    ...typography.bodySm,
    color: colors.heatCore,
    marginTop: spacing.xs,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'flex-end',
    marginTop: spacing.lg,
  },
  button: {
    alignItems: 'center',
    borderRadius: rounded.sm,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  cancelButton: {
    backgroundColor: 'transparent',
  },
  cancelText: {
    ...typography.label,
    color: colors.inkSecondary,
  },
  submitButton: {
    backgroundColor: colors.heatCore,
  },
  submitText: {
    ...typography.label,
    color: colors.void,
    fontWeight: 'bold',
  },
});
