import { fireEvent, waitFor, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import LocationMap from './LocationMap'
import { CENTRO, drag, mapFrame, NORTE } from './testData'
import type { LocationKind, Position } from './types'

const STREET: Position[] = [
  [-61.8, -31.5],
  [-61.5, -31.2],
  [-61.2, -31.5],
]
const name = (number: number) => t('geo.location.mark', { number })

async function show(
  kind: LocationKind,
  positions: Position[],
  onChange?: (positions: Position[]) => void,
) {
  renderApp(
    <LocationMap zones={[CENTRO, NORTE]} kind={kind} positions={positions} onChange={onChange} />,
    { me: makeMe() },
  )
  const frame = await mapFrame(t('geo.location.mapLabel'))
  const marks = () => [...frame.querySelectorAll<HTMLElement>('.leaflet-marker-icon')]
  /** Lines drawn; the zones are the first ones. */
  const paths = () => [...frame.querySelectorAll('path')].slice(2)
  return { frame, marks, paths }
}

it('shows a point with one mark, among the zones', async () => {
  const { frame, marks, paths } = await show('Point', [STREET[0]])

  expect(marks().map((mark) => [mark.title, mark.style.width])).toEqual([[name(1), '20px']])
  expect(paths()).toHaveLength(0)
  expect(within(frame).getByText('Centro')).toBeInTheDocument()
  expect(within(frame).getByText('Norte')).toBeInTheDocument()
  // It is only looked at.
  expect(marks()[0]).not.toHaveAttribute('role')
  expect(frame.parentElement).toHaveStyle({ height: '260px' })
})

it('shows a street as a line, without marks', async () => {
  const { marks, paths } = await show('LineString', STREET)

  expect(marks()).toHaveLength(0)
  expect(paths()).toHaveLength(1)
  expect(paths()[0].getAttribute('d')?.match(/L/g)).toHaveLength(2)
})

it('sets a point: every click moves it', async () => {
  const onChange = vi.fn()
  const { frame, marks, paths } = await show('Point', [STREET[0]], onChange)

  fireEvent.click(frame, { clientX: 400, clientY: 300 })
  expect(onChange).toHaveBeenCalledTimes(1)
  expect(onChange.mock.calls[0][0]).toHaveLength(1)
  expect(onChange.mock.calls[0][0][0]).not.toEqual(STREET[0])
  // A pin to be dragged, and nothing joining it to anything.
  expect(marks().map((mark) => [mark.style.width, mark.getAttribute('role')])).toEqual([
    ['20px', 'button'],
  ])
  expect(paths()).toHaveLength(0)
  expect(frame.parentElement).toHaveStyle({ height: '420px' })
})

it('sets a street: every click adds a point at its end', async () => {
  const onChange = vi.fn()
  const { frame, marks, paths } = await show('LineString', STREET, onChange)

  fireEvent.click(frame, { clientX: 400, clientY: 300 })

  expect(onChange.mock.calls[0][0].slice(0, 3)).toEqual(STREET)
  expect(onChange.mock.calls[0][0]).toHaveLength(4)
  expect(marks().map((mark) => [mark.title, mark.style.width])).toEqual(
    [1, 2, 3].map((number) => [name(number), '18px']),
  )
  // The line being drawn, open, once.
  expect(paths()).toHaveLength(1)
  expect(paths()[0].getAttribute('d')?.endsWith('z')).toBe(false)
})

it('moves only the point that is dragged', async () => {
  const onChange = vi.fn()
  const { marks } = await show('LineString', STREET, onChange)

  drag(marks()[1], [-61.4, -31.3])

  await waitFor(() =>
    expect(onChange).toHaveBeenCalledWith([STREET[0], [-61.4, -31.3], STREET[2]]),
  )
})
