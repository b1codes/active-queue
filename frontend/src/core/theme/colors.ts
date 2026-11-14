/**
 * ActiveQueue Design Tokens — Colors per DESIGN.md §2
 * Derived from OKLCH source values, shipped as React Native hex/rgba equivalents.
 */
export const colors = {
  // Primary
  heatCore: '#FF3B30',
  heatCorona: '#FF9500',

  // Secondary
  signalVerified: '#41D2B3',

  // Tertiary
  emberDeep: '#65201E',

  // Neutral Grounds
  void: '#0C0909',
  substrate: '#1A1615',
  strata: '#282423',

  // Glass Material per LLC Glass & DESIGN.md §2
  glassSurface: 'rgba(255, 255, 255, 0.05)',
  glassEdge: 'rgba(255, 255, 255, 0.12)',
  glassSpecular: 'rgba(255, 255, 255, 0.18)',
  glassSpecularLight: 'rgba(255, 255, 255, 0.28)',

  // Semantic Fills & Edges
  heatCoreMuted: 'rgba(255, 59, 48, 0.4)',
  // Heat Core lifted for text. #FF3B30 text drops to 4.33:1 on Strata, under WCAG AA's
  // 4.5:1; this clears 4.7:1 on every ground. Keep heatCore for fills and borders.
  heatCoreInk: '#FF5147',
  thermalGlowDefault: 'rgba(255, 149, 0, 0.35)',
  modalOverlayBg: 'rgba(12, 9, 9, 0.70)',
  // Behind the Tier 3 glass header. Tier 3 is a 5% tint with no real blur, so without this
  // the header's text sits directly on whatever scrolls beneath it: its subtitle fell to
  // 1.5:1 over a Heat Core button. 0.82 keeps both header lines at AA over pure white.
  glassScrim: 'rgba(12, 9, 9, 0.82)',
  // What every glass surface becomes under Reduce Transparency.
  glassSolid: '#1A1615',
  bannerAlertBg: 'rgba(255, 149, 0, 0.08)',
  bannerAlertEdge: 'rgba(255, 149, 0, 0.25)',

  // Precomputed Lens Composites (One Lens Rule per DESIGN.md §4)
  lensFlat: '#181515',
  lensFlatRaised: '#252221',

  // Ink Typography & Glyphs
  ink: '#F8F4F3',
  inkSecondary: '#CEC9C7',
  inkMuted: '#B2ADAA',
  inkFaint: '#7E7977',
} as const;

export type ColorToken = keyof typeof colors;
