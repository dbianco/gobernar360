import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

import { server } from './server'

// The first render of a lazily loaded dashboard transforms its whole module graph, which
// can take longer than the 1 s default of findBy* queries on a busy machine. Kept below the
// 5 s test timeout, so a query that never matches still reports what it was looking for.
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
