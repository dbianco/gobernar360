import '@testing-library/jest-dom/vitest'
import { act, cleanup, configure, waitFor } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach, vi } from 'vitest'

import i18n from '../i18n'
import { firstScreen } from './render'
import { screenText } from './screen'
import { server } from './server'

// The default of one second is too short when the machine is busy (coverage, mutation
// testing, several suites at once): waits still end as soon as the element shows up.
configure({ asyncUtilTimeout: 5000 })

// jsdom lacks these browser APIs, which Mantine components rely on.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
})
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub
// The email editor (ProseMirror) measures the selection to keep it in view.
const noRects = () => ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] })
const emptyRect = () => ({ x: 0, y: 0, top: 0, left: 0, bottom: 0, right: 0, width: 0, height: 0 })
Range.prototype.getClientRects = noRects as unknown as Range['getClientRects']
Range.prototype.getBoundingClientRect = emptyRect as unknown as Range['getBoundingClientRect']
document.elementFromPoint = () => null
// Textarea autosize listens for web fonts to load.
Object.defineProperty(document, 'fonts', {
  configurable: true,
  value: { addEventListener: vi.fn(), removeEventListener: vi.fn(), ready: Promise.resolve() },
})
window.HTMLElement.prototype.scrollIntoView = vi.fn()
// The maps (Leaflet) draw with SVG, if it looks supported, and need a size to show anything.
Object.defineProperty(SVGElement.prototype, 'createSVGRect', { configurable: true, value: vi.fn() })
for (const [property, size] of [['clientWidth', 800], ['clientHeight', 600]] as const) {
  Object.defineProperty(HTMLElement.prototype, property, {
    configurable: true,
    get(this: HTMLElement) {
      return this.classList.contains('leaflet-container') ? size : 0
    },
  })
}
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo

// Every test runs on the same day, so what a screen shows does not change with the date
// (years offered, "this year"). Only Date is faked: timers run as usual.
const TODAY = new Date(2026, 10, 23, 12, 0)
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: TODAY })
})

// Requests sent and not yet answered: the screen is not final while there are any.
let inFlight = 0
server.events.on('request:start', () => {
  inFlight += 1
})
server.events.on('request:end', () => {
  inFlight -= 1
})

/**
 * Let the last answers arrive and render before reading the screen: no request in flight
 * and no spinner, twice in a row. A screen that never settles is snapshotted as it is.
 */
async function settle() {
  const loading = `[aria-label="${i18n.t('app.loading')}"]`
  for (let round = 0; round < 2; round += 1) {
    await waitFor(() => {
      if (inFlight > 0 || document.querySelector(loading)) throw new Error('still loading')
    }).catch(() => undefined)
    await act(() => new Promise((resolve) => setTimeout(resolve, 0)))
  }
}

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(async ({ expect }) => {
  try {
    if (firstScreen.text) expect(firstScreen.text).toMatchSnapshot('screen at the start')
    await settle()
    // The screen a test ends on, as a snapshot: a label, a message or an empty state that
    // changes or disappears fails the test. Update with `npx vitest -u` after a wanted change.
    const text = screenText()
    if (text) expect(text).toMatchSnapshot('screen at the end')
  } finally {
    firstScreen.text = null
    vi.useRealTimers()
    cleanup()
    server.resetHandlers()
    window.localStorage.clear()
  }
})
afterAll(() => server.close())
