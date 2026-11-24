import { createTheme, MantineProvider, Popover, Tooltip } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

import i18n from '../i18n'
import { AuthProvider } from '../platform/AuthProvider'
import { ConfirmProvider } from '../platform/ConfirmProvider'
import type { Me } from '../platform/types'
import { screenText } from './screen'
import { mockApi, mockApiError } from './server'

// jsdom lays nothing out, so every element has an empty box. Popovers and tooltips would
// then hide themselves as soon as their position is computed, as if their target had
// scrolled out of view, and a test could find a menu open or hidden depending on timing.
const theme = createTheme({
  components: {
    Popover: Popover.extend({ defaultProps: { hideDetached: false } }),
    Tooltip: Tooltip.extend({ defaultProps: { hideDetached: false } }),
  },
})

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
  const view = render(
    // Tests run without transitions: elements appear at once, whatever the Mantine version.
    <MantineProvider env="test" theme={theme}>
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[options.route ?? '/']}>
          <AuthProvider>
            <ConfirmProvider>{ui}</ConfirmProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
  // What shows before any answer arrives (spinners, static labels), for the snapshot
  // src/test/setup.ts takes when the test ends.
  firstScreen.text ??= screenText()
  return view
}

/** The screen of the first render of the current test; setup.ts resets it. */
export const firstScreen: { text: string | null } = { text: null }
