import { expect, it } from 'vitest'

import { numberText, parseNumber } from './numbers'

it.each([
  ['0', '0'],
  ['7', '7'],
  ['1500', '1500'],
  ['-3', '-3'],
  ['1,5', '1.5'],
  ['-0,1234', '-0.1234'],
  ['33.000', '33000'],
  ['1.234.567,89', '1234567.89'],
  ['-12.345', '-12345'],
  ['  42 ', '42'],
])('reads "%s" as people write it here', (typed, number) => {
  expect(parseNumber(typed)).toBe(number)
})

it.each(['', '   '])('takes an empty field for no number', (typed) => {
  expect(parseNumber(typed)).toBeNull()
})

it.each([
  'x',
  '1.5',
  '1500.5',
  '12.34',
  '1.2345',
  '1234.567',
  '.500',
  '1,',
  ',5',
  '1,23456',
  '1,5,5',
  '--1',
  '1 000',
  '5x',
  'x5',
  '1.000x',
  'x1.000',
  '1,x',
  '1.000,x',
  '1.000,12345',
  '-',
])('does not guess what "%s" is', (typed) => {
  expect(parseNumber(typed)).toBeUndefined()
})

it('writes a stored number as it would be typed', () => {
  expect(numberText(1.5)).toBe('1,5')
  expect(numberText(0)).toBe('0')
  expect(numberText(-33000)).toBe('-33000')
  expect(numberText(null)).toBe('')
  expect(numberText(undefined)).toBe('')
})
