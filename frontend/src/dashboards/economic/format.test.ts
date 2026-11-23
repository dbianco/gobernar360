import { expect, it } from 'vitest'

import { formatCuit } from './format'

it('writes a full CUIT with its dashes', () => {
  expect(formatCuit('30711111118')).toBe('30-71111111-8')
})

it('leaves anything that is not a full CUIT as it is', () => {
  expect(formatCuit('')).toBe('')
  expect(formatCuit('3071111111')).toBe('3071111111')
  expect(formatCuit('307111111189')).toBe('307111111189')
})
