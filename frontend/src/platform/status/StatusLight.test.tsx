import { IconLeaf } from '@tabler/icons-react'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { StatusLight } from './StatusLight'

function light(element: React.ReactElement) {
  const { container } = renderApp(element, { me: makeMe() })
  return container.querySelector<HTMLElement>('[data-status]')!
}

it.each([
  ['green', 'tabler-icon-check', 'rgb(255, 255, 255)'],
  ['yellow', 'tabler-icon-alert-triangle', 'rgb(33, 37, 41)'],
  ['red', 'tabler-icon-x', 'rgb(255, 255, 255)'],
] as const)('marks %s with its own sign, besides the color', (color, sign, ink) => {
  const span = light(<StatusLight color={color} size={50} />)

  expect(span).toHaveAttribute('data-status', color)
  expect(span).toHaveStyle({ width: '50px', height: '50px', borderRadius: '50%', color: ink })
  expect(span.style.background).toMatch(new RegExp(`^var\\(--mantine-color-${color}-\\d\\)$`))
  expect(span.style.border).not.toContain('dashed')
  const glyph = span.querySelector('svg')!
  expect(glyph).toHaveClass(sign)
  expect(glyph).toHaveAttribute('width', '29')
  expect(glyph).toHaveAttribute('aria-hidden', 'true')
})

it('is an empty dashed circle without a status', () => {
  const span = light(<StatusLight color={null} size={20} />)

  expect(span).toHaveAttribute('data-status', 'none')
  expect(span.style.background).not.toContain('mantine-color')
  expect(span.style.color).toBe('var(--mantine-color-dimmed)')
  expect(span.style.border).toContain('2px dashed')
  expect(span).toBeEmptyDOMElement()
})

it('shows the icon it is given instead of the sign', () => {
  const span = light(<StatusLight color="red" size={20} icon={IconLeaf} />)

  expect(span.querySelectorAll('svg')).toHaveLength(1)
  expect(span.querySelector('svg')).toHaveClass('tabler-icon-leaf')
})
