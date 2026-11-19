import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { HouseholdDetailPage } from './HouseholdDetailPage'
import {
  BOX,
  LUIS,
  makeDelivery,
  makeHouseholdDetail,
  makeIntervention,
  makePerson,
  makeRegistryPerson,
  page,
  VISIT,
} from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.households.${key}`, options)

function renderDetail(level: AccessLevel = 'editor') {
  mockApi('get', `${BASE}/households/h-1`, makeHouseholdDetail())
  const deliveries = mockApi('get', `${BASE}/deliveries`, page([makeDelivery()]))
  const interventions = mockApi('get', `${BASE}/interventions`, page([makeIntervention()]))
  const view = renderSocial(
    <Routes>
      <Route path="/d/social/households/:id" element={<HouseholdDetailPage />} />
      <Route path="/d/social/households" element={<p>households list</p>} />
    </Routes>,
    { level, route: '/d/social/households/h-1' },
  )
  return { ...view, deliveries, interventions }
}

it('shows the household, its members and the history of all of them', async () => {
  const { deliveries, interventions } = renderDetail('viewer')

  expect(await screen.findByRole('heading', { name: 'Familia Pérez' })).toBeInTheDocument()
  expect(screen.getByText('Belgrano 45')).toBeInTheDocument()
  const head = within(screen.getByRole('row', { name: /Pérez, Juana.*12\.345\.678/ }))
  expect(head.getByText(t('social.relationships.head'))).toBeInTheDocument()
  expect(head.getByRole('link', { name: 'Pérez, Juana' })).toHaveAttribute(
    'href',
    '/d/social/people/sp-1',
  )
  expect(
    within(screen.getByRole('row', { name: /Pérez, Ana/ })).getByText(
      t('social.relationships.child'),
    ),
  ).toBeInTheDocument()
  // The history names who each record belongs to, and nothing is added from here.
  const delivered = within(await screen.findByRole('row', { name: new RegExp(BOX.name) }))
  expect(delivered.getByRole('link', { name: 'Pérez, Juana' })).toBeInTheDocument()
  expect(await screen.findByRole('row', { name: new RegExp(VISIT.name) })).toBeInTheDocument()
  expect(deliveries[0].url.searchParams.get('household_id')).toBe('h-1')
  expect(interventions[0].url.searchParams.get('household_id')).toBe('h-1')
  for (const name of [
    t('app.edit'),
    t('app.delete'),
    label('addMember'),
    t('social.deliveries.add'),
    t('social.interventions.add'),
  ]) {
    expect(screen.queryByRole('button', { name })).toBeNull()
  }
})

it('changes what a member is within the household', async () => {
  const requests = mockApi('put', `${BASE}/households/h-1/members/sp-3`, makeHouseholdDetail())
  renderDetail()
  const user = userEvent.setup()

  const select = await screen.findByLabelText(label('relationshipOf', { name: 'Pérez, Ana' }))
  expect(select).toHaveValue('child')
  await user.selectOptions(select, 'grandchild')

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ relationship: 'grandchild' })
})

it('explains that a household has a single head', async () => {
  mockApiError('put', `${BASE}/households/h-1/members/sp-3`, 409, 'household_has_head')
  renderDetail()
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByLabelText(label('relationshipOf', { name: 'Pérez, Ana' })),
    'head',
  )

  expect(await screen.findByText(t('errors.household_has_head'))).toBeInTheDocument()
})

it('adds a member found by search, skipping people of other households', async () => {
  const elsewhere = makePerson({
    id: 'sp-7',
    person: makeRegistryPerson({ id: 'p-7', full_name: 'Paz, Elena' }),
    household: { id: 'h-9', name: 'Familia Paz' },
  })
  const search = mockApi('get', `${BASE}/people`, page([makePerson(), LUIS, elsewhere]))
  const requests = mockApi('put', `${BASE}/households/h-1/members/sp-2`, makeHouseholdDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addMember') }))
  await user.type(screen.getByRole('textbox', { name: t('social.people.find') }), 'go')
  await user.selectOptions(screen.getByLabelText(label('relationship')), 'partner')
  const add = await screen.findByRole('button', { name: label('addNamed', { name: 'Gómez, Luis' }) })

  expect(search[search.length - 1].url.searchParams.get('q')).toBe('go')
  // Already a member: not offered. In another household: shown, but cannot be added.
  expect(screen.queryByRole('button', { name: label('addNamed', { name: 'Pérez, Juana' }) })).toBeNull()
  expect(screen.getByText(label('inAnother', { name: 'Familia Paz' }))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('addNamed', { name: 'Paz, Elena' }) })).toBeNull()
  await user.click(add)

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ relationship: 'partner' })
})

it('removes a member from the household', async () => {
  const requests = mockApi('delete', `${BASE}/households/h-1/members/sp-3`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('removeNamed', { name: 'Pérez, Ana' }) }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('edits the household', async () => {
  const requests = mockApi('patch', `${BASE}/households/h-1`, makeHouseholdDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const form = within(await screen.findByRole('dialog'))
  await user.clear(form.getByRole('textbox', { name: label('address') }))
  await user.type(form.getByRole('textbox', { name: label('address') }), 'Mitre 10')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Familia Pérez',
    address: 'Mitre 10',
    neighborhood: 'Centro',
  })
})

it('deletes the household after confirming', async () => {
  const requests = mockApi('delete', `${BASE}/households/h-1`, null, 204)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))

  expect(await screen.findByText('households list')).toBeInTheDocument()
  expect(requests).toHaveLength(1)
})

it('offers the first member as head and the following ones as children', async () => {
  const head = { id: 'sp-2', full_name: 'Gómez, Luis' }
  const withHead = makeHouseholdDetail({
    head,
    members: [{ ...head, dni: null, relationship: 'head' }],
  })
  const ana = makePerson({
    id: 'sp-3',
    person: makeRegistryPerson({ id: 'p-3', full_name: 'Gómez, Ana' }),
    household: null,
    relationship: null,
  })
  const puts = mockApi('put', `${BASE}/households/h-1/members/sp-2`, withHead)
  // The household has nobody until the first member is added.
  mockApi('get', `${BASE}/households/h-1`, () =>
    puts.length ? withHead : makeHouseholdDetail({ head: null, members: [], member_count: 0 }),
  )
  mockApi('get', `${BASE}/deliveries`, page([]))
  mockApi('get', `${BASE}/interventions`, page([]))
  mockApi('get', `${BASE}/people`, page([LUIS, ana]))
  const next = mockApi('put', `${BASE}/households/h-1/members/sp-3`, withHead)
  renderSocial(
    <Routes>
      <Route path="/d/social/households/:id" element={<HouseholdDetailPage />} />
    </Routes>,
    { route: '/d/social/households/h-1' },
  )
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addMember') }))
  expect(screen.getByLabelText(label('relationship'))).toHaveValue('head')
  await user.type(screen.getByRole('textbox', { name: t('social.people.find') }), 'gom')
  await user.click(
    await screen.findByRole('button', { name: label('addNamed', { name: 'Gómez, Luis' }) }),
  )
  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ relationship: 'head' })

  await waitFor(() => expect(screen.getByLabelText(label('relationship'))).toHaveValue('child'))
  await user.click(screen.getByRole('button', { name: label('addNamed', { name: 'Gómez, Ana' }) }))
  await waitFor(() => expect(next).toHaveLength(1))
  expect(next[0].body).toEqual({ relationship: 'child' })
})
