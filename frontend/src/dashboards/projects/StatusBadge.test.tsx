import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { StatusBadge } from './StatusBadge'

it.each([
  ['not_started', 'gray'],
  ['in_progress', 'blue'],
  ['delayed', 'red'],
  ['finished', 'green'],
] as const)('names %s next to its color', (status, color) => {
  renderApp(<StatusBadge status={status} />, { me: makeMe() })

  const badge = screen.getByText(t(`projects.status.${status}`)).closest('.mantine-Badge-root')
  expect(badge?.getAttribute('style')).toContain(`--mantine-color-${color}-`)
})
