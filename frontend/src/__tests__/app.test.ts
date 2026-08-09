import { formatDuration } from '../core/utils';

describe('formatDuration', () => {
  it('formats seconds under 1 hour as M:SS', () => {
    expect(formatDuration(42)).toBe('0:42');
    expect(formatDuration(125)).toBe('2:05');
  });

  it('formats seconds over 1 hour as H:MM:SS', () => {
    expect(formatDuration(3665)).toBe('1:01:05');
  });

  it('handles negative or invalid seconds gracefully', () => {
    expect(formatDuration(-10)).toBe('0:00');
    expect(formatDuration(NaN)).toBe('0:00');
  });
});
