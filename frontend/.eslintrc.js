module.exports = {
  extends: ['expo'],
  ignorePatterns: ['.rnstorybook/storybook.requires.ts'],
  rules: {
    'no-console': ['warn', { allow: ['warn', 'error'] }],
  },
};
