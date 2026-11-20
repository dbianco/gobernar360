import { expect, it } from 'vitest'

const sources = import.meta.glob('./**/*.tsx', { query: '?raw', import: 'default', eager: true })

/** Headers that need no explanation: a month, a year, or the label of a row. */
const ALLOWED = [
  /<Table\.Th key=\{month\}>/,
  /<Table\.Th>\{year\}<\/Table\.Th>/,
  /<Table\.Th scope="row"/,
]

it('explains every named column of every dashboard table', () => {
  const plainHeaders = Object.entries(sources)
    .filter(([path]) => !path.includes('.test.'))
    .flatMap(([path, source]) =>
      (source as string)
        .split('\n')
        .map((line, index) => ({ line: line.trim(), where: `${path}:${index + 1}` }))
        // A self-closing header is an unnamed column of row actions.
        .filter(({ line }) => /<Table\.Th[\s>]/.test(line) && !/<Table\.Th\s*\/>/.test(line))
        .filter(({ line }) => !ALLOWED.some((pattern) => pattern.test(line)))
        .map(({ line, where }) => `${where} ${line}`),
    )

  // Use <HelpTh help={...}> so the column carries its explanation.
  expect(plainHeaders).toEqual([])
})
