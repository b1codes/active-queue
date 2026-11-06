// ESLint 9 flat config: Expo's base rules + typescript-eslint "strict" for TS sources.
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');
const tseslint = require('typescript-eslint');

// Expo's flat config already registers the @typescript-eslint plugin, so take only the
// *rules* from typescript-eslint's strict preset to avoid a duplicate-plugin error.
const strictRules = Object.assign({}, ...tseslint.configs.strict.map((c) => c.rules ?? {}));

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['.rnstorybook/storybook.requires.ts', 'coverage/**', 'dist/**', '.expo/**'],
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    rules: {
      ...strictRules,
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      // HTML-entity escaping is a DOM concern: JSX entities compile to plain characters
      // and React Native <Text> never parses HTML, so apostrophes in copy are fine.
      'react/no-unescaped-entities': 'off',
    },
  },
  {
    // jest.mock() factories must use require(); test helpers may patch console and use
    // non-null assertions on values the test itself just set up.
    files: ['jest.setup.ts', 'src/__tests__/**', 'src/test-utils/**', '__mocks__/**'],
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      'no-console': 'off',
    },
  },
  {
    files: ['*.config.js', 'babel.config.js', 'metro.config.js'],
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
]);
