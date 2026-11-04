/** @type {import('jest').Config} */
module.exports = {
  preset: 'jest-expo',
  clearMocks: true,
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  transformIgnorePatterns: [
    '/node_modules/(?!(.pnpm|react-native|@react-native|@react-native-community|expo|@expo|@expo-google-fonts|react-navigation|@react-navigation|@sentry/react-native|native-base|immer|react-redux))',
    '/node_modules/react-native-reanimated/plugin/',
  ],
  // Tests live under src/ only: anything under app/ is treated as a route by expo-router.
  testMatch: ['<rootDir>/src/**/__tests__/**/*.test.{ts,tsx}'],
  // Measure every source file, not just the ones a test happens to import.
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    'app/**/*.{ts,tsx}',
    '!**/*.stories.tsx',
    '!**/__tests__/**',
    '!src/test-utils/**',
    '!**/*.d.ts',
  ],
  // Floors for the whole app (src/ + app/). Raise them as coverage grows; never lower them
  // to get a PR through. Measured 2026-11-03: ~97% lines, ~88% branches.
  coverageThreshold: {
    global: { lines: 90, statements: 90, functions: 90, branches: 80 },
  },
  coverageReporters: ['text-summary', 'text', 'lcov', 'json'],
};
