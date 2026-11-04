module.exports = {
  extends: ['expo'],
  ignorePatterns: ['.rnstorybook/storybook.requires.ts', 'coverage/'],
  rules: {
    'no-console': ['warn', { allow: ['warn', 'error'] }],
  },
  overrides: [
    {
      // jest.mock() factories must use require(); test setup may patch console.
      files: ['jest.setup.ts', 'src/__tests__/**', 'src/test-utils/**', '__mocks__/**'],
      rules: {
        '@typescript-eslint/no-require-imports': 'off',
        'no-console': 'off',
      },
    },
  ],
};
