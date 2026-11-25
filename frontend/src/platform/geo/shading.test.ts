import { expect, it } from 'vitest'

import { shadeOf, SHADES, shadeSteps } from './shading'

it('has no steps when there is nothing to shade', () => {
  expect(shadeSteps([])).toEqual([])
  expect(shadeSteps([0, null, '0.00'])).toEqual([])
})

it('uses the darkest shades when there are few different values', () => {
  expect(shadeSteps([7, 7, 0])).toEqual([{ color: SHADES[3], from: 7, to: 7 }])
  expect(shadeSteps([2, 9])).toEqual([
    { color: SHADES[2], from: 2, to: 2 },
    { color: SHADES[3], from: 9, to: 9 },
  ])
})

it('splits the values evenly, so one large zone does not hide the rest', () => {
  expect(shadeSteps([1, 2, 3, 4, 5, 6, 7, 1000])).toEqual([
    { color: SHADES[0], from: 1, to: 2 },
    { color: SHADES[1], from: 3, to: 4 },
    { color: SHADES[2], from: 5, to: 6 },
    { color: SHADES[3], from: 7, to: 1000 },
  ])
})

it('shades amounts that come as text', () => {
  const steps = shadeSteps(['100.50', '20.00', null])

  expect(shadeOf('20.00', steps)).toBe(SHADES[2])
  expect(shadeOf('100.50', steps)).toBe(SHADES[3])
})

it('leaves zero and hidden values unshaded', () => {
  const steps = shadeSteps([1, 2])

  expect(shadeOf(0, steps)).toBeNull()
  expect(shadeOf(null, steps)).toBeNull()
})
