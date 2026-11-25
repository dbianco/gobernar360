import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { mapFrame } from '../platform/geo/testData'
import { t } from '../test/render'
import { mockApi } from '../test/server'
import { MapPage as EconomicMap } from './economic/MapPage'
import { FOOD, SHOP } from './economic/testData'
import { renderEconomic } from './economic/testRender'
import { MapPage as ProjectsMap } from './projects/MapPage'
import { TERM } from './projects/testData'
import { renderProjects } from './projects/testRender'
import { MapPage as SocialMap } from './social/MapPage'
import { renderSocial } from './social/testRender'

const FEATURES = { restricted: false, total: 0, features: [], clusters: [], truncated: false }
const mockFeatures = (path: string) => mockApi('get', `/dashboards/${path}/features`, FEATURES)
const last = (requests: { url: URL }[]) => {
  const query = Object.fromEntries(requests[requests.length - 1].url.searchParams)
  delete query.bbox
  delete query.zoom
  return query
}

it('filters the projects of the term on the map as in their list', async () => {
  const requests = mockFeatures('projects/geo/projects')
  renderProjects(<ProjectsMap />)
  const user = userEvent.setup()
  await mapFrame(t('geo.map.labels.projects.projects'))
  await waitFor(() => expect(last(requests)).toEqual({ term_id: TERM.id }))

  await user.selectOptions(
    screen.getByRole('combobox', { name: t('projects.filters.status') }),
    t('projects.status.delayed'),
  )
  await user.type(screen.getAllByRole('searchbox')[0], 'p')

  await waitFor(() =>
    expect(last(requests)).toEqual({ term_id: TERM.id, status: 'delayed', q: 'p' }),
  )
  expect(
    screen.getByRole('region', { name: t('geo.unzoned.titles.projects.projects') }),
  ).toBeInTheDocument()
})

it('filters the actors on the map as in their list', async () => {
  const requests = mockFeatures('economic/geo/actors')
  renderEconomic(<EconomicMap />)
  const user = userEvent.setup()
  await mapFrame(t('geo.map.labels.economic.actors'))
  await waitFor(() => expect(last(requests)).toEqual({}))

  const filter = (key: string) => screen.getByRole('combobox', { name: t(`economic.actors.${key}`) })
  await screen.findByRole('option', { name: SHOP.name })
  await user.selectOptions(filter('type'), SHOP.name)
  await user.selectOptions(filter('sector'), FOOD.name)
  await user.type(screen.getAllByRole('searchbox')[0], 'p')

  await waitFor(() =>
    expect(last(requests)).toEqual({
      q: 'p',
      actor_type_id: SHOP.id,
      sector_id: FOOD.id,
    }),
  )
  expect(
    screen.getByRole('region', { name: t('geo.unzoned.titles.economic.actors') }),
  ).toBeInTheDocument()
})

it('shows households on the map to those who load data', async () => {
  const requests = mockFeatures('social/geo/households')
  renderSocial(<SocialMap />, { level: 'editor' })
  const user = userEvent.setup()
  await mapFrame(t('geo.map.labels.social.households'))

  await user.type(screen.getAllByRole('searchbox')[0], 's')

  await waitFor(() => expect(last(requests)).toEqual({ q: 's' }))
  expect(
    screen.getByRole('region', { name: t('geo.unzoned.titles.social.households') }),
  ).toBeInTheDocument()
})

it('shows viewers counts by zone only, and asks for nothing else', async () => {
  const features = mockFeatures('social/geo/households')
  const unzoned = mockApi('get', '/dashboards/social/geo/households/unzoned', {
    items: [],
    total: 0,
  })
  renderSocial(<SocialMap />, { level: 'viewer' })

  expect(await screen.findByText(t('geo.map.restricted'))).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByLabelText(t('app.loading'))).toBeNull())
  expect(screen.queryByRole('searchbox')).toBeNull()
  expect([features.length, unzoned.length]).toEqual([0, 0])
})
