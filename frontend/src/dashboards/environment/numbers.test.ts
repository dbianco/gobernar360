import { expect, it } from 'vitest'

import { numberText, parseNumber } from './numbers'

it.each([
  ['0', '0'],
  ['7', '7'],
  ['-12', '-12'],
  ['1500', '1500'],
  ['1500,5', '1500.5'],
  ['-0,1234', '-0.1234'],
  ['1.500', '1500'],
  ['33.000', '33000'],
  ['-123.456.789', '-123456789'],
  ['1.234.567,8901', '1234567.8901'],
  ['  42,5 ', '42.5'],
])('reads %j as %s', (typed, number) => {
  expect(parseNumber(typed)).toBe(number)
})

it.each(['', '   '])('reads %j as an empty field', (typed) => {
  expect(parseNumber(typed)).toBeNull()
})

it.each([
  'abc',
  '-',
  ',5',
  '5,',
  '1.5',
  '1500.5',
  '1234.567',
  '1.50',
  '1.5000',
  '.500',
  '1,23456',
  '1.500,23456',
  '1.500,',
  '1,2,3',
  '12a',
  'a12',
  '1.500a',
  'a1.500',
  'a.500',
  '1.abc',
  '1,a',
  '1.500,a',
  '--1',
  '1 500',
])('does not take %j for a number', (typed) => {
  expect(parseNumber(typed)).toBeUndefined()
})

it.each([
  [null, ''],
  [undefined, ''],
  [0, '0'],
  [-2.5, '-2,5'],
  [1500, '1500'],
])('writes %s as %j', (value, text) => {
  expect(numberText(value)).toBe(text)
})
