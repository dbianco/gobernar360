// Mutation testing pilot: `npm run mutation`. The report opens from reports/mutation/index.html.
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  testRunner: 'vitest',
  // Each mutant runs only the tests that import the file and reach the changed code.
  vitest: { configFile: 'vite.config.ts', related: true },
  coverageAnalysis: 'perTest',
  // The pilot: how indicators are formatted, judged and masked.
  mutate: [
    'src/platform/indicators/format.ts',
    'src/platform/indicators/Sparkline.tsx',
    'src/platform/indicators/IndicatorCard.tsx',
    'src/platform/format.ts',
    'src/public/PublicIndicatorCard.tsx',
  ],
  // Stryker rewrites tsconfig paths that point outside its sandbox through the TypeScript 5
  // API, which TypeScript 7 no longer has. Ours point nowhere outside, so it is skipped.
  tsconfigFile: '',
  concurrency: 2,
  timeoutMS: 20000,
  reporters: ['clear-text', 'progress', 'html', 'json'],
  htmlReporter: { fileName: 'reports/mutation/index.html' },
  jsonReporter: { fileName: 'reports/mutation/mutation.json' },
  // Anchored: `reports` alone would also leave out src/platform/reports.
  ignorePatterns: ['/coverage', '/dist', '/e2e', '/test-results', '/playwright-report', '/reports'],
  // Report only, for now: the pilot sets no minimum score.
  thresholds: { high: 80, low: 60, break: null },
}
