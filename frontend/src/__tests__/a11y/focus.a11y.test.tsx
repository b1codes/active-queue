/**
 * Focus order and focus containment.
 *
 * iOS VoiceOver orders elements spatially, so whole-screen order needs the device (see
 * docs/manual-qa.md). A single-column sheet has the same spatial and tree order, though,
 * so its order can be checked here, along with how it confines and releases focus.
 */
import React from 'react';
import { AccessibilityInfo } from 'react-native';
import { act, fireEvent, screen } from '@testing-library/react-native';
import type { TestInstance } from 'test-renderer';
import { renderWithProviders, resetStores } from '@/test-utils';
import { AddSourceModal } from '@/features/queue/components/AddSourceModal';
import { useQueueStore } from '@/features/queue/queueStore';

/** What VoiceOver would stop on, in tree order: accessible elements and standalone text. */
function focusOrder(root: TestInstance): string[] {
  const out: string[] = [];
  const text = (n: TestInstance): string =>
    n.children.map((c) => (typeof c === 'string' ? c : text(c))).join('');
  const walk = (n: TestInstance) => {
    if (n.props.accessibilityElementsHidden || n.props.importantForAccessibility === 'no-hide-descendants') return;
    const label = n.props.accessibilityLabel as string | undefined;
    if (n.props.accessible === true || n.type === 'TextInput') {
      out.push(label ?? text(n).trim());
      return;
    }
    if (n.type === 'Text') {
      const t = text(n).trim();
      if (t) out.push(label ?? t);
      return;
    }
    n.children.forEach((c) => typeof c !== 'string' && walk(c));
  };
  walk(root);
  return out;
}

function modal(): TestInstance {
  let n: TestInstance | null = screen.getByRole('header', { name: 'Add Content Source' });
  while (n && n.type !== 'Modal') n = n.parent;
  if (!n) throw new Error('not inside a Modal');
  return n;
}

beforeEach(() => resetStores());

describe('AddSourceModal', () => {
  it('renders inside a Modal, the separate window that confines VoiceOver', async () => {
    await renderWithProviders(<AddSourceModal visible onClose={jest.fn()} />);
    expect(modal().props.visible).toBe(true);
  });

  it('reads top to bottom: title, instructions, field, then the actions', async () => {
    await renderWithProviders(<AddSourceModal visible onClose={jest.fn()} />);
    expect(focusOrder(modal())).toEqual([
      'Add Content Source',
      expect.stringMatching(/^Paste a YouTube playlist URL/),
      'YouTube playlist URL or ID',
      'Cancel adding content source',
      'Add source',
    ]);
  });

  it('puts the error between the field and the actions, and speaks it', async () => {
    const announce = jest.spyOn(AccessibilityInfo, 'announceForAccessibility').mockImplementation(() => {});
    await renderWithProviders(<AddSourceModal visible onClose={jest.fn()} />);
    await act(async () => useQueueStore.setState({ addSourceError: 'Playlist not found or is private.' }));
    expect(focusOrder(modal()).slice(2, 4)).toEqual(['YouTube playlist URL or ID', 'Playlist not found or is private.']);
    expect(screen.getByRole('alert')).toHaveTextContent('Playlist not found or is private.');
    expect(announce).toHaveBeenCalledWith('Playlist not found or is private.');
  });

  it('does not announce while hidden', async () => {
    const announce = jest.spyOn(AccessibilityInfo, 'announceForAccessibility').mockImplementation(() => {});
    useQueueStore.setState({ addSourceError: 'stale' });
    await renderWithProviders(<AddSourceModal visible={false} onClose={jest.fn()} />);
    expect(announce).not.toHaveBeenCalled();
  });

  it('closes on the VoiceOver escape gesture and on the hardware back action', async () => {
    const onClose = jest.fn();
    await renderWithProviders(<AddSourceModal visible onClose={onClose} />);
    const sheet = screen.getByRole('header', { name: 'Add Content Source' }).parent!;
    await fireEvent(sheet, 'accessibilityEscape');
    expect(onClose).toHaveBeenCalledTimes(1);
    await act(async () => modal().props.onRequestClose());
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
