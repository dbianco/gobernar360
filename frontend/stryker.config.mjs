// Mutation testing of the app code: `npm run test:mutation`, reports in reports/mutation/.
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  testRunner: 'vitest',
  plugins: ['@stryker-mutator/vitest-runner', './stryker-ignore-styling.mjs'],
  ignorers: ['styling'],
  // The same files the coverage report counts: app code, not tests or their helpers.
  mutate: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.test.{ts,tsx}',
    '!src/test/**',
    '!src/**/testData.ts',
    '!src/**/testRender.tsx',
    '!src/main.tsx',
    '!src/**/types.ts',
  ],
  coverageAnalysis: 'perTest',
  // Later runs only test again the mutants whose code or tests changed.
  incremental: true,
  incrementalFile: 'reports/mutation/stryker-incremental.json',
  // Code that only runs while a module loads (constants, tables of labels) would need the
  // whole suite for every mutant.
  ignoreStatic: true,
  // Stryker reads tsconfig.json only to fix paths that point outside the project, and it
  // does so with the JavaScript API of TypeScript, which TypeScript 7 no longer has. None of
  // our paths leave the project, so it is pointed at a file that does not exist.
  tsconfigFile: 'no-tsconfig-rewrite.json',
  concurrency: 4,
  timeoutMS: 20000,
  // The first run goes through every test in a single process.
  dryRunTimeoutMinutes: 60,
  reporters: ['clear-text', 'progress', 'html', 'json'],
  htmlReporter: { fileName: 'reports/mutation/index.html' },
  jsonReporter: { fileName: 'reports/mutation/mutation.json' },
  tempDirName: '.stryker-tmp',
}
