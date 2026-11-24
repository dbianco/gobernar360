import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { PublicationPage } from './PublicationPage'

const STATE = {
  enabled: true,
  slug: 'noetinger',
  small_count_threshold: 5,
  dashboards: [
    {
      key: 'projects',
      name: 'Proyectos',
      published: true,
      indicators: [
        { key: 'projects.delayed', name: 'x', unit: null, aggregate: true, published: true },
        { key: 'projects.active', name: 'x', unit: null, aggregate: false, published: false },
      ],
    },
    {
      key: 'social',
      name: 'Social',
      published: false,
      indicators: [
        { key: 'social.people', name: 'x', unit: null, aggregate: true, published: false },
      ],
    },
  ],
}

const indicator = (key: string) =>
  screen.getByRole('checkbox', {
    name: t('publication.indicator', { name: t(`overview.indicators.${key}`) }),
  })
// The switch's label goes on with its description.
const dashboard = (key: string) =>
  screen.getByLabelText(
    t('publication.dashboard', { name: t(`${key}.title`) }) + t('publication.dashboardHint'),
  )

function renderPublication() {
  mockApi('get', '/publication', STATE)
  renderApp(<PublicationPage />, { me: makeMe({ isAdmin: true }) })
}

it('shows the page settings and what is published', async () => {
  renderPublication()

  expect(await screen.findByLabelText(t('publication.slug'), { exact: false })).toHaveValue(
    'noetinger',
  )
  expect(screen.getByLabelText(t('publication.enabled'))).toBeChecked()
  expect(screen.getByRole('link', { name: t('publication.open') })).toHaveAttribute(
    'href',
    '/p/noetinger',
  )
  expect(dashboard('projects')).toBeChecked()
  expect(dashboard('social')).not.toBeChecked()
  expect(indicator('projects.delayed')).toBeChecked()
  // Not aggregate: never selectable.
  expect(indicator('projects.active')).toBeDisabled()
  expect(screen.getByText(t('publication.notAggregate'))).toBeInTheDocument()
  // Its dashboard is not published.
  expect(indicator('social.people')).toBeDisabled()
})

it('saves the page settings', async () => {
  renderPublication()
  const saves = mockApi('put', '/publication/settings', STATE)
  const user = userEvent.setup()

  const slug = await screen.findByLabelText(t('publication.slug'), { exact: false })
  await user.clear(slug)
  await user.type(slug, 'transparencia')
  await user.click(screen.getByLabelText(t('publication.enabled')))
  await user.click(screen.getByRole('button', { name: t('publication.save') }))

  await waitFor(() => expect(saves).toHaveLength(1))
  expect(saves[0].body).toEqual({
    enabled: false,
    slug: 'transparencia',
    small_count_threshold: 5,
  })
})

it('says so when the address is taken', async () => {
  renderPublication()
  mockApiError('put', '/publication/settings', 409, 'slug_taken')

  await userEvent.click(await screen.findByRole('button', { name: t('publication.save') }))

  expect(await screen.findByText(t('errors.slug_taken'))).toBeInTheDocument()
})

it('publishes and unpublishes dashboards and indicators at once', async () => {
  renderPublication()
  const dashboards = mockApi('put', '/publication/dashboards/social', STATE)
  const indicators = mockApi('put', '/publication/indicators/projects.delayed', STATE)
  const user = userEvent.setup()

  await screen.findByLabelText(t('publication.slug'), { exact: false })
  await user.click(dashboard('social'))
  await waitFor(() => expect(dashboards).toHaveLength(1))
  await user.click(indicator('projects.delayed'))

  await waitFor(() => expect(indicators).toHaveLength(1))
  expect(dashboards[0].body).toEqual({ published: true })
  expect(indicators[0].body).toEqual({ published: false })
})
