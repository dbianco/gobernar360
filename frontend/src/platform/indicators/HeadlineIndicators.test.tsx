import { screen, waitFor, within } from '@testing-library/react'
import { expect, it } from 'vitest'

import { makeEvolution, makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { HeadlineIndicators } from './HeadlineIndicators'

const URL = '/dashboards/projects/evolution'
const me = makeMe({ dashboards: { projects: 'viewer' } })

it("shows every indicator of the dashboard's catalogue with its evolution", async () => {
  mockApi('get', URL, [
    makeEvolution('projects.active', 10, null, { change_previous_month: 2 }),
    makeEvolution('projects.delayed', 3, null, { higher_is_better: false }),
  ])
  renderApp(<HeadlineIndicators dashboardKey="projects" />, { me })

  const section = await screen.findByRole('region', { name: t('indicators.title') })
  const cards = section.querySelectorAll('[data-indicator]')
  expect([...cards].map((card) => card.getAttribute('data-indicator'))).toEqual([
    'projects.active',
    'projects.delayed',
  ])
  expect(
    within(section).getByText(t('indicators.vsPreviousMonth', { change: '+2' })),
  ).toBeInTheDocument()
})

it('shows nothing before the dashboard has any data', async () => {
  const requests = mockApi('get', URL, [makeEvolution('projects.active', null)])
  renderApp(<HeadlineIndicators dashboardKey="projects" />, { me })

  await waitFor(() => expect(requests).toHaveLength(1))
  // Let the answer render.
  await new Promise((resolve) => setTimeout(resolve, 50))
  expect(screen.queryByRole('region', { name: t('indicators.title') })).not.toBeInTheDocument()
})

it('shows the error when the indicators cannot be read', async () => {
  mockApiError('get', URL, 403, 'forbidden')
  renderApp(<HeadlineIndicators dashboardKey="projects" />, { me })

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})
