import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { CENTRO, mapFrame, NORTE } from './testData'
import type { ProfileSection } from './types'
import { ZoneProfile } from './ZoneProfile'

const label = (key: string) => t(`geo.profile.${key}`)
const zone = { id: 'z-1', name: 'Centro' }
const section = (overrides: Partial<ProfileSection>): ProfileSection => ({
  dashboard_key: 'economic',
  record_key: 'actors',
  metrics: [{ key: 'actors', unit: null }],
  grouping: null,
  values: { actors: 4 },
  groups: [],
  suppressed: false,
  threshold: null,
  ...overrides,
})
const ECONOMIC = section({
  grouping: 'sector',
  groups: [
    { name: 'Alimentos', count: 3 },
    { name: null, count: 1 },
  ],
})
const SOCIAL = section({
  dashboard_key: 'social',
  record_key: 'households',
  metrics: [{ key: 'households', unit: null }],
  values: { households: null },
  suppressed: true,
  threshold: 5,
})

async function choose(name: string) {
  const user = userEvent.setup()
  await user.selectOptions(await screen.findByRole('combobox', { name: t('geo.zone') }), name)
  return user
}

it('combines what every dashboard has in the zone chosen', async () => {
  mockApi('get', '/zones', [CENTRO, NORTE])
  mockApi('get', '/overview/zones/z-1', {
    zone,
    // One of a dashboard this build does not know is left out.
    sections: [ECONOMIC, SOCIAL, section({ dashboard_key: 'nuevo' })],
  } as never)
  renderApp(<ZoneProfile />, { me: makeMe() })

  await choose('Centro')

  const economic = within(await screen.findByRole('region', { name: t('economic.title') }))
  expect(economic.getByText('4')).toBeInTheDocument()
  expect(economic.getByText('Por sector: Alimentos 3 · Sin sector 1')).toBeInTheDocument()
  const social = within(screen.getByRole('region', { name: t('social.title') }))
  expect(social.getByText(t('geo.breakdown.hidden'))).toBeInTheDocument()
  expect(social.getByText(t('geo.breakdown.hiddenNote', { count: 5 }))).toBeInTheDocument()
  expect(screen.getAllByRole('heading', { level: 4 })).toHaveLength(2)
})

it('chooses a zone on the map too, and none again from the list', async () => {
  mockApi('get', '/zones', [CENTRO, NORTE])
  mockApi('get', '/overview/zones/z-1', { zone, sections: [] })
  const norte = mockApi('get', '/overview/zones/z-2', { zone, sections: [] })
  renderApp(<ZoneProfile />, { me: makeMe() })
  const user = await choose('Centro')
  expect(await screen.findByText(label('empty'))).toBeInTheDocument()

  const frame = await mapFrame(label('mapLabel'))
  fireEvent.click(frame.querySelectorAll('path')[1])
  await waitFor(() => expect(norte).toHaveLength(1))
  expect(screen.getByRole('combobox')).toHaveValue('z-2')

  await user.selectOptions(screen.getByRole('combobox'), '')
  expect(screen.queryByRole('region', { name: label('mapLabel') })).toBeNull()
})

it('is not there until the municipality has zones', async () => {
  const requests = mockApi('get', '/zones', [])
  renderApp(<ZoneProfile />, { me: makeMe() })

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(screen.queryByText(label('title'))).toBeNull()
})

it('says why the profile or the zones cannot be shown', async () => {
  mockApi('get', '/zones', [CENTRO])
  mockApiError('get', '/overview/zones/z-1', 404, 'not_found')
  const { unmount } = renderApp(<ZoneProfile />, { me: makeMe() })
  await choose('Centro')
  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
  unmount()

  mockApiError('get', '/zones', 500, 'boom')
  renderApp(<ZoneProfile />, { me: makeMe() })
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
