import { expect, it } from 'vitest'

import { moved } from './order'

it('moves one element a place up or down and leaves the list given as it was', () => {
  const list = ['a', 'b', 'c']

  expect(moved(list, 1, -1)).toEqual(['b', 'a', 'c'])
  expect(moved(list, 1, 1)).toEqual(['a', 'c', 'b'])
  expect(list).toEqual(['a', 'b', 'c'])
})
