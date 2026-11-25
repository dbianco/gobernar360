import { expect, it } from 'vitest'

import { withFormer } from './directory'

const ANA = { id: 'u-1', full_name: 'Ana' }
const LEO = { id: 'u-2', full_name: 'Leo' }

it('adds those chosen who are no longer members, once', () => {
  expect(withFormer([ANA], [ANA, LEO])).toEqual([LEO, ANA])
  expect(withFormer(undefined, [LEO])).toEqual([LEO])
  expect(withFormer([ANA], [])).toEqual([ANA])
})
