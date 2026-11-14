/**
 * Entry point of the visual-regression build (ClickUp 86bcxruz4). The Xcode bundle phase
 * uses it when ENTRY_FILE points here (scripts/ios-sim-build.sh screenshots). Production
 * builds never include it: their entry is expo-router/entry.
 */
import { freezeClock } from './catalog';

// Before any app module can read the time. Imports are hoisted, so everything else loads
// through the require below, after the clock is frozen.
freezeClock();
// eslint-disable-next-line @typescript-eslint/no-require-imports
require('./register');
