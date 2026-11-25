import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import L from 'leaflet'
import { type ReactNode, useEffect, useState } from 'react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import type { View } from './api'
import { GeoMap } from './GeoMap'
import { ClickCatcher, GoTo, LinesLayer, MarkersLayer, OutlineLayer, ViewWatcher, ZonesLayer } from './layers'
import type { Bounds } from './geometry'
import { useLeafletMap } from './mapContext'
import { boundary, mapFrame, square } from './testData'
import type { Position } from './types'

const CONTENT: Position[] = [
  [-62, -32],
  [-61, -32],
  [-61, -31],
]
let map: L.Map

/** Hands over the map the layers draw on. */
function Grab({ onMap }: { onMap: (map: L.Map) => void }) {
  const grabbed = useLeafletMap()
  useEffect(() => onMap(grabbed), [grabbed, onMap])
  return null
}

const remember = (grabbed: L.Map) => {
  map = grabbed
}

async function show(children: ReactNode, props: Partial<Parameters<typeof GeoMap>[0]> = {}) {
  const view = renderApp(
    <GeoMap label="Mapa" bounds={[-62, -32, -61, -31]} {...props}>
      <Grab onMap={remember} />
      {children}
    </GeoMap>,
    { me: makeMe() },
  )
  return { frame: await mapFrame('Mapa'), ...view }
}

it('opens on what it is given, and not too close on a single place', async () => {
  await show(null)
  const bounds = map.getBounds()
  expect(bounds.contains([-32, -62]) && bounds.contains([-31, -61])).toBe(true)
  expect(bounds.getEast() - bounds.getWest()).toBeLessThan(4)
})

it('opens on a single place at the zoom of its block', async () => {
  await show(null, { bounds: [-61.5, -31.5, -61.5, -31.5] })

  expect(map.getZoom()).toBe(16)
  expect(map.getCenter().lat).toBeCloseTo(-31.5, 4)
  expect(map.getMaxZoom()).toBe(19)
})

it('measures itself again when its frame changes size, but not while hidden', async () => {
  const watched: ResizeObserverCallback[] = []
  const original = window.ResizeObserver
  window.ResizeObserver = class {
    constructor(callback: ResizeObserverCallback) {
      watched.push(callback)
    }
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
  const { frame } = await show(null)
  const measured = vi.spyOn(map, 'invalidateSize')
  const resize = () => watched.forEach((callback) => callback([], {} as ResizeObserver))

  resize()
  expect(measured).toHaveBeenCalledTimes(1)
  Object.defineProperty(frame, 'clientWidth', { configurable: true, value: 0 })
  resize()
  expect(measured).toHaveBeenCalledTimes(1)
  window.ResizeObserver = original
})

it.each([
  [false, true],
  [true, false],
])('zooms with a double click only while not drawing (drawing: %s)', async (drawing, zooms) => {
  await show(null, { drawing })

  expect(map.doubleClickZoom.enabled()).toBe(zooms)
})

it('tells the visible area within the world, rounded, and every time it moves', async () => {
  const views: View[] = []
  await show(<ViewWatcher onChange={(view) => views.push(view)} />)
  expect(views).toHaveLength(1)
  expect(views[0].zoom).toBe(map.getZoom())
  for (const number of views[0].bbox.split(',')) expect(number).toMatch(/^-?\d+(\.\d{1,6})?$/)

  act(() => {
    map.setView([0, 0], 0, { animate: false })
  })

  const { bbox, zoom } = views[views.length - 1]
  const [west, south, east, north] = bbox.split(',').map(Number)
  expect([west, east, zoom]).toEqual([-180, 180, 0])
  expect(south).toBeGreaterThanOrEqual(-90)
  expect(north).toBeLessThanOrEqual(90)
  expect(north).toBeGreaterThan(80)
})

it('goes where it is told, and no closer than streets', async () => {
  function Buttons() {
    const [bounds, setBounds] = useState<Bounds | null>(null)
    return (
      <>
        <button onClick={() => setBounds([-61.5, -31.5, -61.5, -31.5])}>go</button>
        <GoTo bounds={bounds} />
      </>
    )
  }
  await show(<Buttons />)
  const before = map.getZoom()
  expect(before).toBeLessThan(12)

  fireEvent.click(screen.getByRole('button', { name: 'go' }))

  await waitFor(() => expect(map.getZoom()).toBe(18))
  expect(map.getCenter().lng).toBeCloseTo(-61.5, 4)
})

it('tells where it is clicked, in the order GeoJSON takes and to ten centimetres', async () => {
  const clicked: Position[] = []
  const { frame } = await show(<ClickCatcher onClick={(position) => clicked.push(position)} />)

  fireEvent.click(frame, { clientX: 400, clientY: 300 })

  const [[longitude, latitude]] = clicked
  expect(longitude).toBeCloseTo(-61.5, 1)
  expect(latitude).toBeCloseTo(-31.5, 1)
  expect(String(longitude)).toMatch(/^-61\.\d{1,6}$/)
  // Past the edge of the world it is still a place of it.
  act(() => {
    map.fire('click', { latlng: L.latLng(10, 190) })
  })
  expect(clicked[1]).toEqual([-170, 10])
})

it('draws zones shaded, dashed or chosen, and writes their labels as they are', async () => {
  const chosen: string[] = []
  const zone = (id: string, x: number) => ({ id, boundary: boundary(square(x, -32, 0.3)) })
  const { frame } = await show(
    <ZonesLayer
      zones={[
        { ...zone('a', -62), label: '<b>A</b>', fill: '#123456' },
        { ...zone('b', -61.6), label: 'B', dashed: true },
        { ...zone('c', -61.3), selected: true },
      ]}
      onSelect={(id) => chosen.push(id)}
    />,
  )

  const [a, b, c] = frame.querySelectorAll('path')
  expect([a, b, c].map((path) => path.getAttribute('fill'))).toEqual(['#123456', '#868e96', '#868e96'])
  expect([a, b, c].map((path) => path.getAttribute('fill-opacity'))).toEqual(['0.7', '0', '0'])
  expect([a, b, c].map((path) => path.getAttribute('stroke-dasharray'))).toEqual([null, '6 5', null])
  expect(c.getAttribute('stroke')).not.toBe(a.getAttribute('stroke'))
  expect(Number(c.getAttribute('stroke-width'))).toBeGreaterThan(Number(a.getAttribute('stroke-width')))
  expect(screen.getByText('<b>A</b>')).toBeInTheDocument()
  expect(frame.querySelectorAll('.leaflet-tooltip')).toHaveLength(2)
  // Under the marks, and out of the way of the mouse.
  const pane = screen.getByText('B').closest<HTMLElement>('.leaflet-pane')!
  expect([pane.style.zIndex, pane.style.pointerEvents]).toEqual(['590', 'none'])
  fireEvent.click(b)
  expect(chosen).toEqual(['b'])
})

it('does not take clicks on zones nobody can choose', async () => {
  const { frame } = await show(
    <ZonesLayer zones={[{ id: 'a', boundary: boundary(square(-62, -32)), fill: null }]} />,
  )

  const path = frame.querySelector('path')!
  expect(path).not.toHaveClass('leaflet-interactive')
  expect(path.getAttribute('fill')).toBe('none')
})

it('makes buttons of the marks that do something, and of no other', async () => {
  const pressed: string[] = []
  const mark = (key: string, extra = {}) => ({
    key,
    position: [-61.5, -31.5] as Position,
    name: `Marca ${key}`,
    kind: 'pin' as const,
    ...extra,
  })
  const { frame } = await show(
    <MarkersLayer
      markers={[
        mark('a', { text: '<i>3</i>', onClick: () => pressed.push('a') }),
        mark('b', { kind: 'corner', onDrag: () => undefined }),
        mark('c', { kind: 'middle' }),
      ]}
    />,
  )

  const [a, b, c] = ['a', 'b', 'c'].map((key) => frame.querySelector<HTMLElement>(`[title="Marca ${key}"]`)!)
  expect([a, b, c].map((element) => element.getAttribute('aria-label'))).toEqual([
    'Marca a',
    'Marca b',
    'Marca c',
  ])
  expect([a, b, c].map((element) => element.getAttribute('role'))).toEqual(['button', 'button', null])
  expect(a).toHaveTextContent('<i>3</i>')
  expect([a, b, c].map((element) => element.style.width)).toEqual(['20px', '18px', '14px'])
  // What is being edited is over the rest: corners over the middles of the sides.
  const height = (element: HTMLElement) => Number(element.style.zIndex)
  expect(height(b)).toBeGreaterThan(height(c))
  expect(height(c)).toBeGreaterThan(height(a))

  for (const key of ['Enter', ' ', 'x', 'Tab']) fireEvent.keyDown(a, { key })
  fireEvent.click(a)
  expect(pressed).toEqual(['a', 'a', 'a'])
  // One that is only dragged does nothing when pressed.
  fireEvent.keyDown(b, { key: 'Enter' })
  expect(pressed).toHaveLength(3)
})

it('draws only the lines among the geometries', async () => {
  const opened: string[] = []
  const { frame } = await show(
    <LinesLayer
      lines={[
        { key: 'p', geometry: { type: 'Point', coordinates: CONTENT[0] } },
        { key: 'a', geometry: { type: 'LineString', coordinates: CONTENT }, onClick: () => opened.push('a') },
        { key: 'b', geometry: { type: 'LineString', coordinates: CONTENT } },
      ]}
    />,
  )

  const paths = frame.querySelectorAll('path')
  expect(paths).toHaveLength(2)
  expect([...paths].map((path) => path.classList.contains('leaflet-interactive'))).toEqual([true, false])
  expect([...paths].map((path) => path.getAttribute('fill'))).toEqual(['none', 'none'])
  fireEvent.click(paths[0])
  expect(opened).toEqual(['a'])
})

it.each([
  [CONTENT.slice(0, 2), false, 'none', false],
  [CONTENT, false, expect.stringMatching(/^#/), true],
  // A street does not close on itself.
  [CONTENT, true, 'none', false],
])('closes the outline from three corners on', async (corners, open, fill, closed) => {
  const { frame } = await show(<OutlineLayer corners={corners} open={open} />)

  const path = frame.querySelector('path')!
  expect(path.getAttribute('fill')).toEqual(fill)
  expect(path.getAttribute('d')!.endsWith('z')).toBe(closed)
  expect(path).not.toHaveClass('leaflet-interactive')
})

it('leaves nothing drawn when it goes', async () => {
  const zones = mockApi('get', '/zones', [])
  const { unmount } = await show(<OutlineLayer corners={CONTENT} />)
  const removed = vi.spyOn(map, 'remove')

  unmount()

  await waitFor(() => expect(removed).toHaveBeenCalledOnce())
  expect(zones).toHaveLength(0)
})
