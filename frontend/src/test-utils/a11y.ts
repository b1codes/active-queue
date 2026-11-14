/**
 * Accessibility auditor for rendered component and screen trees.
 *
 * Walks the host tree that RNTL renders and reports what VoiceOver, Dynamic Type and low-vision
 * users would actually hit. Each rule maps to a WCAG 2.2 criterion or SPEC §11.4:
 *
 *   role        an interactive element has no accessibilityRole (4.1.2)
 *   name        an interactive element has no label and no text to announce (4.1.2)
 *   state       a radio/checkbox/switch has no `checked`, a tab no `selected`, or a button
 *               showing a spinner isn't marked `busy` (4.1.2)
 *   nested      an interactive or accessible element sits inside another accessible element.
 *               iOS exposes only the outer one, so VoiceOver can never reach the inner (2.1.1)
 *   input-label a TextInput relies on its placeholder, which VoiceOver stops reading once
 *               the field has text (3.3.2)
 *   target      a touch target declares a size under 44x44pt, hitSlop included (SPEC §11.4)
 *   font-cap    text has no Dynamic Type ceiling, a ceiling above fontScale.max, or opts
 *               out of scaling altogether (1.4.4)
 *   clip        at its ceiling, text no longer fits the fixed-height box around it (1.4.4)
 *   decorative  an icon or emoji-only Text that VoiceOver would stop on and read as a glyph
 *               name ("satellite antenna"), outside any labelled element (1.1.1)
 *   contrast    text under 4.5:1 (3:1 if large), or an icon under 3:1, against the
 *               composited background (1.4.3, 1.4.11)
 *
 * The checks read declared props and styles, not native layout, so they're a floor: anything
 * that needs real rendering (VoiceOver reading order, actual wrapping) stays in
 * docs/manual-qa.md.
 */
import { StyleSheet, type TextStyle, type ViewStyle } from 'react-native';
import type { TestInstance } from 'test-renderer';
import { screen } from '@testing-library/react-native';
import { colors, fontScale } from '@/core/theme';
import {
  AA_LARGE,
  AA_NON_TEXT,
  AA_NORMAL,
  contrastRatio,
  flatten,
  isLargeText,
} from './contrast';

export type A11yRule =
  | 'role'
  | 'name'
  | 'state'
  | 'nested'
  | 'input-label'
  | 'target'
  | 'font-cap'
  | 'clip'
  | 'decorative'
  | 'contrast';

export interface A11yViolation {
  rule: A11yRule;
  message: string;
  where: string;
}

export interface AuditOptions {
  /** Opaque color behind the tree. Every screen and sheet sits on Void. */
  background?: string;
  /** Rules to skip, with the reason recorded at the call site. */
  skip?: A11yRule[];
}

/** iOS minimum touch target per SPEC §11.4 and Apple's HIG. */
export const MIN_TARGET = 44;
/** iOS default text size when a style sets none. */
const DEFAULT_FONT_SIZE = 14;
/** The largest iOS text size (AX5) is ~3.1x the default. Uncapped text can reach it. */
const UNCAPPED_SCALE = 3.1;

const INTERACTIVE_ROLES = new Set([
  'button', 'link', 'tab', 'checkbox', 'radio', 'switch', 'adjustable', 'menuitem',
  'togglebutton', 'combobox', 'search', 'imagebutton', 'keyboardkey', 'spinbutton', 'slider',
]);
const CHECKED_ROLES = new Set(['radio', 'checkbox', 'switch']);
const ICON_FONT = /^(ionicons|material|materialcommunityicons|feather|fontawesome\w*|antdesign|entypo|evilicons|foundation|octicons|simplelineicons|zocial)$/i;

type Node = TestInstance;

function isNode(n: unknown): n is Node {
  return typeof n === 'object' && n !== null;
}

function children(n: Node): Node[] {
  return n.children.filter(isNode);
}

function style<T extends ViewStyle | TextStyle>(n: Node): T {
  return (StyleSheet.flatten(n.props.style) ?? {}) as T;
}

function role(n: Node): string | undefined {
  return (n.props.accessibilityRole ?? n.props.role) as string | undefined;
}

function a11yState(n: Node): Record<string, unknown> {
  return {
    ...(n.props.accessibilityState ?? {}),
    ...(n.props['aria-checked'] !== undefined ? { checked: n.props['aria-checked'] } : {}),
    ...(n.props['aria-selected'] !== undefined ? { selected: n.props['aria-selected'] } : {}),
    ...(n.props['aria-busy'] !== undefined ? { busy: n.props['aria-busy'] } : {}),
    ...(n.props['aria-disabled'] !== undefined ? { disabled: n.props['aria-disabled'] } : {}),
  };
}

function isHiddenFromA11y(n: Node): boolean {
  return (
    n.props.accessibilityElementsHidden === true ||
    n.props.importantForAccessibility === 'no-hide-descendants' ||
    n.props['aria-hidden'] === true
  );
}

function isIcon(n: Node): boolean {
  if (n.type !== 'Text') return false;
  const family = style<TextStyle>(n).fontFamily;
  return typeof family === 'string' && ICON_FONT.test(family);
}

const EMOJI_ONLY = /^[\p{Extended_Pictographic}\p{Emoji_Component}\uFE0F\u200D\s]+$/u;

/** Text whose only characters are emoji. They paint in their own colors, not `color`. */
function isEmojiOnly(n: Node): boolean {
  if (n.type !== 'Text') return false;
  const text = textContent(n);
  return text.length > 0 && EMOJI_ONLY.test(text) && !/^[\d#*\s]+$/.test(text);
}

function isInteractive(n: Node): boolean {
  if (n.type === 'TextInput' || n.type === 'RCTSwitch') return true;
  if (n.type !== 'View' && n.type !== 'Text') return false;
  const actions = (n.props.accessibilityActions ?? []) as { name: string }[];
  return (
    typeof n.props.onClick === 'function' ||
    typeof n.props.onPress === 'function' ||
    actions.some((a) => a.name === 'activate') ||
    (n.props.accessible === true && INTERACTIVE_ROLES.has(role(n) ?? ''))
  );
}

/** Screen-reader text: string children of every descendant Text, icons excluded. */
function textContent(n: Node): string {
  if (isIcon(n)) return '';
  return n.children
    .map((c) => (typeof c === 'string' ? c : textContent(c)))
    .join('')
    .trim();
}

function accessibleName(n: Node): string {
  const label = (n.props.accessibilityLabel ?? n.props['aria-label']) as string | undefined;
  return (label ?? textContent(n)).trim();
}

function describe(n: Node): string {
  const parts: string[] = [];
  let cur: Node | null = n;
  while (cur && parts.length < 3) {
    const id = cur.props.testID as string | undefined;
    const label = (cur.props.accessibilityLabel as string | undefined) ?? undefined;
    const text = cur.type === 'Text' ? textContent(cur) : '';
    const tag = id ? `#${id}` : label ? `"${label}"` : text ? `'${text.slice(0, 40)}'` : '';
    if (tag || cur === n) parts.unshift(`${cur.type}${tag ? ` ${tag}` : ''}`);
    cur = cur.parent;
  }
  return parts.join(' > ');
}

function edge(s: ViewStyle, side: 'Top' | 'Bottom', base: 'padding' | 'borderWidth'): number {
  const key = base === 'padding' ? `padding${side}` : `border${side}Width`;
  const axis = base === 'padding' ? 'paddingVertical' : undefined;
  const v = (s as Record<string, unknown>)[key] ?? (axis ? (s as Record<string, unknown>)[axis] : undefined) ??
    (s as Record<string, unknown>)[base];
  return typeof v === 'number' ? v : 0;
}

function hitSlop(n: Node): { v: number; h: number } {
  const hs = n.props.hitSlop as number | { top?: number; bottom?: number; left?: number; right?: number } | undefined;
  if (typeof hs === 'number') return { v: hs * 2, h: hs * 2 };
  if (!hs) return { v: 0, h: 0 };
  return { v: (hs.top ?? 0) + (hs.bottom ?? 0), h: (hs.left ?? 0) + (hs.right ?? 0) };
}

/** Text style with React Native's Text-to-Text inheritance applied. */
function effectiveTextStyle(n: Node): TextStyle {
  const chain: TextStyle[] = [];
  let cur: Node | null = n;
  while (cur) {
    if (cur.type === 'Text') chain.unshift(style<TextStyle>(cur));
    cur = cur.parent;
  }
  return Object.assign({}, ...chain);
}

function hasDescendant(n: Node, pred: (d: Node) => boolean): boolean {
  return children(n).some((c) => pred(c) || hasDescendant(c, pred));
}

function ancestors(n: Node): Node[] {
  const out: Node[] = [];
  let cur = n.parent;
  while (cur) {
    out.push(cur);
    cur = cur.parent;
  }
  return out;
}

/** Background fills from the root down to `n`, for compositing onto the base color. */
function backgroundBehind(n: Node): string[] {
  return [n, ...ancestors(n)]
    .reverse()
    .map((a) => style<ViewStyle>(a).backgroundColor)
    .filter((c): c is string => typeof c === 'string');
}

function isDisabled(n: Node): boolean {
  return [n, ...ancestors(n)].some((a) => a11yState(a).disabled === true);
}

function outermostText(n: Node): boolean {
  return n.type === 'Text' && n.parent?.type !== 'Text';
}

/** Audit a rendered tree. Returns every violation; `expectAccessible` turns them into a failure. */
export function auditAccessibility(root: Node, options: AuditOptions = {}): A11yViolation[] {
  const base = options.background ?? colors.void;
  const skip = new Set(options.skip ?? []);
  const out: A11yViolation[] = [];
  const report = (rule: A11yRule, n: Node, message: string) => {
    if (!skip.has(rule)) out.push({ rule, message, where: describe(n) });
  };

  const visit = (n: Node, insideAccessible: Node | null, hidden: boolean) => {
    const nowHidden = hidden || isHiddenFromA11y(n);
    const interactive = isInteractive(n);
    const accessible = n.props.accessible === true;

    if (!nowHidden) {
      if ((interactive || accessible) && insideAccessible) {
        report(
          'nested',
          n,
          `is inside accessible element ${describe(insideAccessible)}, so VoiceOver can't focus it. ` +
            'Drop `accessible` from the wrapper or move this element out of it.'
        );
      }

      if (interactive && n.type !== 'TextInput' && n.type !== 'RCTSwitch') {
        const r = role(n);
        if (!r) report('role', n, 'is pressable but has no accessibilityRole, so VoiceOver won\'t say "button".');
        if (!accessibleName(n)) report('name', n, 'is pressable but has no accessibilityLabel or text to announce.');
        const state = a11yState(n);
        if (r && CHECKED_ROLES.has(r) && typeof state.checked !== 'boolean' && state.checked !== 'mixed') {
          report('state', n, `has role "${r}" but no accessibilityState.checked.`);
        }
        if (r === 'tab' && typeof state.selected !== 'boolean') {
          report('state', n, 'has role "tab" but no accessibilityState.selected.');
        }
        if (hasDescendant(n, (d) => d.type === 'ActivityIndicator') && state.busy !== true) {
          report('state', n, 'shows a spinner but isn\'t marked accessibilityState.busy.');
        }
      }

      if (outermostText(n) && (isIcon(n) || isEmojiOnly(n)) && !insideAccessible) {
        report(
          'decorative',
          n,
          'is a lone glyph VoiceOver would stop on. Hide it (accessibilityElementsHidden + ' +
            'importantForAccessibility="no") or put it inside a labelled element.'
        );
      }

      if (n.type === 'TextInput' && !n.props.accessibilityLabel && !n.props['aria-label']) {
        report('input-label', n, 'has no accessibilityLabel. Its placeholder stops being read once it has text.');
      }
    }

    if (interactive && n.type === 'View') {
      const s = style<ViewStyle>(n);
      const slop = hitSlop(n);
      const h = typeof s.height === 'number' ? s.height : s.minHeight;
      const w = typeof s.width === 'number' ? s.width : s.minWidth;
      if (typeof h === 'number' && h + slop.v < MIN_TARGET) {
        report('target', n, `is ${h + slop.v}pt tall including hitSlop; the minimum is ${MIN_TARGET}pt.`);
      }
      if (typeof w === 'number' && w + slop.h < MIN_TARGET) {
        report('target', n, `is ${w + slop.h}pt wide including hitSlop; the minimum is ${MIN_TARGET}pt.`);
      }
    }

    if (n.type === 'Text') checkText(n, base, report);
    if (n.type === 'TextInput') checkInput(n, base, report);

    const nextInside = insideAccessible ?? (accessible || interactive ? n : null);
    // Text children of a Text are one run, not separate elements.
    for (const c of children(n)) visit(c, n.type === 'Text' ? insideAccessible : nextInside, nowHidden);
  };

  visit(root, null, false);
  return out;
}

function checkText(n: Node, base: string, report: (r: A11yRule, n: Node, m: string) => void) {
  const s = effectiveTextStyle(n);
  const icon = isIcon(n);
  const ownText = n.children.filter((c): c is string => typeof c === 'string').join('').trim();

  // Contrast for every Text that paints its own characters, nested runs included.
  if ((ownText || icon) && !isEmojiOnly(n) && !isDisabled(n)) {
    const bg = flatten(base, backgroundBehind(n));
    const fg = typeof s.color === 'string' ? s.color : '#000000';
    const ratio = contrastRatio(fg, bg);
    const size = s.fontSize ?? DEFAULT_FONT_SIZE;
    const need = icon ? AA_NON_TEXT : isLargeText(size, s.fontWeight) ? AA_LARGE : AA_NORMAL;
    if (ratio + 1e-9 < need) {
      report(
        'contrast',
        n,
        `${icon ? 'icon' : `${size}pt text`} ${fg} on ${rgbHex(bg)} is ${ratio.toFixed(2)}:1; ` +
          `needs ${need}:1.${typeof s.color === 'string' ? '' : ' (no color set, so it renders black)'}`
      );
    }
  }

  if (!outermostText(n) || icon || isEmojiOnly(n)) return;

  const cap = n.props.maxFontSizeMultiplier as number | undefined;
  if (n.props.allowFontScaling === false) {
    report('font-cap', n, 'sets allowFontScaling={false}, so it ignores the iOS text size setting.');
    return;
  }
  if (cap === undefined || cap === null || cap === 0) {
    report('font-cap', n, 'has no maxFontSizeMultiplier. Render it with the shared Text component.');
  } else if (cap > fontScale.max) {
    report('font-cap', n, `caps at ${cap}x, above fontScale.max (${fontScale.max}x).`);
  }

  const scale = cap && cap > 0 ? cap : UNCAPPED_SCALE;
  const fontSize = s.fontSize ?? DEFAULT_FONT_SIZE;
  const lineHeight = s.lineHeight ?? fontSize * 1.2;
  const needed = lineHeight * scale * Math.max(1, (n.props.numberOfLines as number | undefined) ?? 1);
  for (const a of ancestors(n)) {
    const as = style<ViewStyle>(a);
    if (typeof as.height !== 'number') continue;
    const room =
      as.height - edge(as, 'Top', 'padding') - edge(as, 'Bottom', 'padding') -
      edge(as, 'Top', 'borderWidth') - edge(as, 'Bottom', 'borderWidth');
    if (needed > room + 0.5) {
      report(
        'clip',
        n,
        `needs ${needed.toFixed(1)}pt at ${scale}x text size but sits in a fixed ${as.height}pt-high ` +
          `${describe(a)} (${room}pt inside). Use minHeight, or a lower cap such as fontScale.compact.`
      );
    }
    break;
  }
}

function checkInput(n: Node, base: string, report: (r: A11yRule, n: Node, m: string) => void) {
  const s = style<TextStyle>(n);
  const bg = flatten(base, backgroundBehind(n));
  const fg = typeof s.color === 'string' ? s.color : '#000000';
  if (contrastRatio(fg, bg) < AA_NORMAL) {
    report('contrast', n, `input text ${fg} on ${rgbHex(bg)} is ${contrastRatio(fg, bg).toFixed(2)}:1; needs 4.5:1.`);
  }
  const ph = n.props.placeholderTextColor as string | undefined;
  if (n.props.placeholder && (!ph || contrastRatio(ph, bg) < AA_NORMAL)) {
    report(
      'contrast',
      n,
      ph
        ? `placeholder ${ph} on ${rgbHex(bg)} is ${contrastRatio(ph, bg).toFixed(2)}:1; needs 4.5:1.`
        : 'has a placeholder but no placeholderTextColor, so it falls back to the system gray.'
    );
  }
  if (n.props.allowFontScaling === false) {
    report('font-cap', n, 'sets allowFontScaling={false}, so it ignores the iOS text size setting.');
  }
}

function rgbHex({ r, g, b }: { r: number; g: number; b: number }): string {
  return `#${[r, g, b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')}`;
}

export function formatViolations(violations: A11yViolation[]): string {
  return violations.map((v) => `  [${v.rule}] ${v.where}\n      ${v.message}`).join('\n');
}

/** Fail the test with every violation in the tree (the current screen by default). */
export function expectAccessible(root: Node | null = screen.root, options?: AuditOptions): void {
  if (!root) throw new Error('expectAccessible: nothing is rendered');
  const violations = auditAccessibility(root, options);
  if (violations.length > 0) {
    throw new Error(`${violations.length} accessibility violation(s):\n${formatViolations(violations)}`);
  }
}
