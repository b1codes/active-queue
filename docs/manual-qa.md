# Manual QA checklist

This lists only what automated tests can't cover. Everything else runs in CI (see
[testing.md](testing.md)). Run this checklist on a physical iPhone before each App Store
submission, and after any change to the files named in a section.

Record each run (date, build, device, iOS version, pass/fail per item) in the release ticket.

## Accessibility

What CI already checks on every PR, so you don't need to here:
- roles, labels and states on every control
- that no control is hidden inside a grouped element
- touch targets of at least 44pt
- a Dynamic Type ceiling on all text, and fixed-height boxes that fit it
- WCAG AA contrast, including text on glass
- Reduce Transparency
- the Reduce Motion source guard
- the add-source sheet's reading order, escape gesture, and error announcement

Details are in [testing.md](testing.md#accessibility-tests).

Devices: one small screen (iPhone SE or 13 mini) and one large (Pro Max or Plus), on the
lowest and newest supported iOS.

### VoiceOver

Re-run after changes to `app/`, `src/core/components/`, or `src/features/*/components/`.

- [ ] **Reading order on every screen.** VoiceOver orders elements by position on screen,
      which Jest can't see. Swipe right through each screen from the top. The glass header
      should come first, even though it renders after the list. Nothing should be skipped
      or read twice.
- [ ] **Session handoff, eyes closed.** From the queue, pick a card, pick an activity,
      start, open the tracker (or skip), launch media, come back, and mark complete. Then
      repeat with Abandon. You should never need to look at the screen.
- [ ] **Feed card options.** Double-tap and hold a feed card, and separately use its
      "Options for…" button. Both open the Hide from Queue alert, and Hide removes the card.
      Swipe-to-hide is not VoiceOver-operable, so this is the path SPEC §11.4 requires.
- [ ] **Add source sheet.**
  - Opening the sheet moves focus into it.
  - Swiping can't reach the queue behind it.
  - A two-finger Z (escape) closes it.
  - A bad URL speaks the error.
- [ ] **Sync progress.** While a sync runs, the progress bar reads its count ("250 of
      about 1284 items synced"), and Cancel is reachable.
- [ ] **Headings rotor.** The rotor's Headings list includes:
  - the title on every screen
  - each section on time blocks and settings
  - each step on the session checklist

### Dynamic Type

Settings > Accessibility > Display & Text Size > Larger Text. Check at the largest standard
size, then at AX2, where `fontScale.max` (2.0) stops text growth.

- [ ] Nothing is cut off mid-line or overlaps on the queue, time blocks, session checklist,
      history, settings and sign-in. CI checks only fixed-height boxes. Real line wrapping
      needs the device.
- [ ] Every screen still scrolls to its last control.
- [ ] Header, duration pills and chips stop growing at 1.5x and stay inside their shapes.

### Visual settings

- [ ] **Reduce Transparency on**, iOS 26+ build (Tier 1 native glass): the header and the
      add-source sheet go opaque. Toggle the setting with the app open. It should take
      effect without a relaunch.
- [ ] **Reduce Motion on:** tapping a card shows no heat glow and no press-scale. Skeleton
      rows hold a static color, and the active-session dot doesn't pulse.
- [ ] **Tier 1 header legibility:** scroll a bright thumbnail and the red Start button under
      the header. Its title and subtitle must stay readable. CI checks this only for Tier 3,
      because the native material's vibrancy is drawn by iOS.
- [ ] **Increase Contrast on:** text and borders stay visible. The app doesn't adapt to it
      yet, so this is a regression check only.
- [ ] **Bold Text on:** labels still fit their buttons.

## Platform hand-offs

Covered by [e2e_device_validation.md](testing/e2e_device_validation.md) until the E2E suite
(ClickUp 86bcxruy6) lands:
- Sign in with Apple
- the custom auth domain
- Apple Fitness and tracker URL-scheme hand-off
- the deep-link device matrix

## Performance

What CI already checks, so you don't need to here:
- Firestore reads per request and YouTube quota per sync
- API latency, rate limiting and memory under load
- container cold start
- how many feed rows mount, and which re-render
- the 2-layer blur budget
- JS-thread animation
- bundle size

Details are in [testing.md](testing.md#performance-and-load-tests).

The checks below need a real device. Use a **release** build (`eas build --profile
preview`): debug builds run the JS unoptimized and every number is wrong. Use the oldest
supported iPhone, since it is the one that drops frames first. Turn on the Performance
Monitor from the dev menu, or record a Core Animation trace in Instruments.

- **Launch:** cold launch (app killed, then tapped) to a usable feed in under 2 s on a warm
  API. The API's own cold start is measured nightly; on a staging cold start, add it.
- **Long feed:** sync a 1,000+ item playlist, then fling the feed top to bottom and back.
  It holds 60 fps (120 on ProMotion) with no blank rows after the fling settles.
- **Glass while scrolling:** scroll content under the glass header with Tier 1 (iOS 26+)
  and with Tier 3. Neither drops frames, and the header text stays legible.
- **Sync in the background of the UI:** start a 5,000-item sync and scroll the feed while it
  runs. Scrolling stays smooth and the progress card advances. A pause of up to a minute is
  the rate limit and expected.
- **Animations:** ThermalGlow and ChromaticPulse stay smooth while the JS thread is busy:
  start a sync, then press and hold a card. The UI-thread frame rate doesn't drop.

Record the device, iOS version, build and fps for each in the release ticket. The E2E
simulator harness (ClickUp 86bcxruy6) is where these can become automated traces.
