import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

import { server } from './server'

// Screens that render a whole dashboard wait for its lazily loaded routes, which a cold test
// worker transforms on first use: under a full parallel run on a busy machine that can take
// more than the default second. Stays well below Vitest's five seconds per test.
configure({ asyncUtilTimeout: 3000 })

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
window.HTMLElement.prototype.scrollIntoView = vi.fn()
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  window.localStorage.clear()
})
afterAll(() => server.close())
