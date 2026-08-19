module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      [
        'module-resolver',
        {
          root: ['./'],
          alias: {
            '@': './src',
            '@app': './app',
          },
        },
      ],
      // babel-preset-expo auto-adds react-native-worklets/plugin (which
      // react-native-reanimated/plugin now forwards to) whenever
      // react-native-worklets is installed — an explicit entry here would
      // double-run the worklets transform.
    ],
  };
};
