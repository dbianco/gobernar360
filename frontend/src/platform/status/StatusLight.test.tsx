import { IconBulb } from '@tabler/icons-react'
import { render } from '@testing-library/react'
import { expect, it } from 'vitest'

import { StatusLight } from './StatusLight'
import type { StatusColor } from './types'

function light(color: StatusColor | null, icon?: typeof IconBulb) {
  const { container } = render(<StatusLight color={color} size={50} icon={icon} />)
  const element = container.querySelector<HTMLElement>('span')!
  return { element, glyph: element.querySelector('svg') }
}

it.each([
  ['green', 'tabler-icon-check', 'green-8', 'rgb(255, 255, 255)'],
  ['yellow', 'tabler-icon-alert-triangle', 'yellow-5', 'rgb(33, 37, 41)'],
  ['red', 'tabler-icon-x', 'red-8', 'rgb(255, 255, 255)'],
] as const)('tells %s by its mark as well as by its color', (color, mark, background, ink) => {
  const { element, glyph } = light(color)

  expect(element).toHaveAttribute('data-status', color)
  expect(glyph).toHaveClass(mark)
  // The name is next to the light: the mark itself is not read.
  expect(glyph).toHaveAttribute('aria-hidden', 'true')
  expect(element.style.background).toContain(background)
  expect(element.style.color).toBe(ink)
  expect(element.style.borderStyle).toBe('none')
})

it('is an empty outline without a color', () => {
  const { element, glyph } = light(null)

  expect(element).toHaveAttribute('data-status', 'none')
  expect(glyph).toBeNull()
  expect(element.style.background).not.toContain('mantine-color')
  expect(element.style.border).toContain('dashed')
})

it("shows a dashboard's icon instead of the mark, in proportion to its size", () => {
  const { element, glyph } = light('red', IconBulb)

  expect(glyph).toHaveClass('tabler-icon-bulb')
  expect(glyph).toHaveAttribute('width', '29')
  expect([element.style.width, element.style.height, element.style.borderRadius]).toEqual([
    '50px',
    '50px',
    '50%',
  ])
  expect(light(null, IconBulb).glyph).toHaveClass('tabler-icon-bulb')
})
