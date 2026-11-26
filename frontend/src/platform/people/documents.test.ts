import { expect, it } from 'vitest'

import { cuilHasDni, documentQuery, formatCuil, validCuil, validDni } from './documents'

it.each([
  ['20-12345678-6', true],
  ['20123456786', true],
  [' 20.12345678 6', true],
  ['27-12345678-0', true],
  ['20-12345678-7', false],
  ['2012345678', false],
  ['201234567866', false],
  ['20-1234567a-6', false],
  ['', false],
  // Ten digits no CUIL starts with: no last digit makes them one.
  ['20000000010', false],
  ['20000000011', false],
])('takes %s for a CUIL: %s', (typed, valid) => {
  expect(validCuil(typed)).toBe(valid)
})

it.each([
  ['12.345.678', true],
  ['123456', true],
  ['123456789', true],
  ['12345', false],
  ['1234567890', false],
  ['1234567a', false],
])('takes %s for a DNI: %s', (typed, valid) => {
  expect(validDni(typed)).toBe(valid)
})

it('knows the document inside a CUIL, however each is typed', () => {
  expect(cuilHasDni('20-12345678-6', '12.345.678')).toBe(true)
  expect(cuilHasDni('20012345675', '1234567')).toBe(true)
  expect(cuilHasDni('20123456786', '12345679')).toBe(false)
})

it('asks the registry about one or the other', () => {
  expect(documentQuery('12.345.678')).toEqual({ dni: '12345678' })
  expect(documentQuery('20-12345678-6')).toEqual({ cuil: '20123456786' })
  expect(documentQuery('20-12345678-7')).toBeNull()
  expect(documentQuery('12')).toBeNull()
  expect(documentQuery('')).toBeNull()
})

it('writes a CUIL with its dashes', () => {
  expect(formatCuil('20123456786')).toBe('20-12345678-6')
  expect(formatCuil(null)).toBe('—')
})
