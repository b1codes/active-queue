/**
 * WCAG 2.2 contrast math for the accessibility suite.
 *
 * Colors are parsed from the forms the theme and components actually use (#rgb, #rrggbb,
 * #rrggbbaa, rgb(), rgba(), a few CSS names), and translucent layers are composited onto
 * whatever sits beneath them before a ratio is taken, so text on glass and on rgba banner
 * fills is measured against the color a user really sees.
 */

export interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

const NAMED: Record<string, string> = {
  black: '#000000',
  white: '#ffffff',
  transparent: '#00000000',
};

export function parseColor(input: string): Rgba {
  const value = (NAMED[input.trim().toLowerCase()] ?? input).trim();
  let m = /^#([0-9a-f]{3,8})$/i.exec(value);
  if (m) {
    let hex = m[1];
    if (hex.length === 3 || hex.length === 4) hex = [...hex].map((c) => c + c).join('');
    if (hex.length !== 6 && hex.length !== 8) throw new Error(`Unparseable color: ${input}`);
    const n = (i: number) => parseInt(hex.slice(i, i + 2), 16);
    return { r: n(0), g: n(2), b: n(4), a: hex.length === 8 ? n(6) / 255 : 1 };
  }
  m = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(value);
  if (m) {
    return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] };
  }
  throw new Error(`Unparseable color: ${input}`);
}

/** Source-over composite of `top` onto an opaque `bottom`. */
export function composite(top: Rgba, bottom: Rgba): Rgba {
  const a = top.a;
  return {
    r: top.r * a + bottom.r * (1 - a),
    g: top.g * a + bottom.g * (1 - a),
    b: top.b * a + bottom.b * (1 - a),
    a: 1,
  };
}

/** Composite a stack of layers, listed bottom first, onto an opaque base. */
export function flatten(base: string, layers: string[]): Rgba {
  return layers.reduce((acc, layer) => composite(parseColor(layer), acc), parseColor(base));
}

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

export function luminance({ r, g, b }: Rgba): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio. A translucent foreground is composited onto the background first. */
export function contrastRatio(fg: Rgba | string, bg: Rgba | string): number {
  const b = typeof bg === 'string' ? parseColor(bg) : bg;
  if (b.a < 1) throw new Error('contrastRatio needs an opaque background; composite it first');
  const f = composite(typeof fg === 'string' ? parseColor(fg) : fg, b);
  const [hi, lo] = [luminance(f), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * WCAG "large text": at least 18pt regular or 14pt bold. React Native sizes are iOS points
 * at 1x (1pt = 1.333px), so the CSS-px thresholds of 24px / 18.66px apply directly.
 */
export function isLargeText(fontSize: number, fontWeight: string | number | undefined): boolean {
  const weight = fontWeight === 'bold' ? 700 : Number(fontWeight ?? 400);
  return fontSize >= 24 || (fontSize >= 18.66 && weight >= 700);
}

export const AA_NORMAL = 4.5;
export const AA_LARGE = 3;
/** WCAG 1.4.11: icons and other meaningful non-text graphics. */
export const AA_NON_TEXT = 3;
