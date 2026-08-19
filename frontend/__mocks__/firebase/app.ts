// Manual mock for the "firebase/app" subpath used under Jest.
//
// The real Firebase JS SDK ships an "exports" map whose react-native/browser
// conditions point at ESM builds not meant for a CommonJS Jest runtime — see
// package.json's jest.transformIgnorePatterns comment for the full story.
// None of this project's tests exercise real Firebase behavior (they mock
// the app's own auth store / API client), so the SDK is stubbed out entirely
// rather than fought into parsing.
export const initializeApp = jest.fn(() => ({}));
export const getApps = jest.fn(() => []);
export const getApp = jest.fn(() => ({}));
