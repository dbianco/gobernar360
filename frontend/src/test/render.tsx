import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

import i18n from '../i18n'
import { AuthProvider } from '../platform/AuthProvider'
import type { Me } from '../platform/types'
import { mockApi, mockApiError } from './server'

/** Translate a key the same way components do, so tests do not hard-code copy. */
export const t = (key: string, options: Record<string, unknown> = {}): string =>
  i18n.t(key, options)

/**
 * Render inside every provider the app uses.
 * `me` is the signed-in user (null means signed out); omit it to mock /auth/me yourself.
 */
export function renderApp(ui: ReactElement, options: { route?: string; me?: Me | null } = {}) {
  if (options.me === null) mockApiError('get', '/auth/me', 401, 'not_authenticated')
  else if (options.me) mockApi('get', '/auth/me', options.me)

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    // Without transitions and portals: a tooltip caught mid-transition by jsdom stayed hidden.
    <MantineProvider env="test">
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[options.route ?? '/']}>
          <AuthProvider>{ui}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}
