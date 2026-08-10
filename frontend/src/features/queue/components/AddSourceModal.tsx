import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
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
      <View style={styles.overlay}>
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
                >
                  <Text style={styles.cancelText}>Cancel</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  onPress={handleAdd}
                  style={[styles.button, styles.submitButton]}
                  disabled={isAddingSource || !urlOrId.trim()}
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
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    flex: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  modalContent: {
    backgroundColor: colors.substrate,
    borderColor: colors.glassEdge,
    borderRadius: rounded.md,
    borderWidth: 1,
    padding: spacing.lg,
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
    padding: spacing.md,
  },
  errorText: {
    ...typography.bodySm,
    color: colors.heatCore,
    marginTop: spacing.xs,
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: spacing.lg,
  },
  button: {
    borderRadius: rounded.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  cancelButton: {
    backgroundColor: 'transparent',
    marginRight: spacing.sm,
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
