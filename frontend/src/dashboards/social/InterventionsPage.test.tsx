import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { closeDialog } from '../../test/dialogs'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { InterventionsPage } from './InterventionsPage'
import { INTERVIEW, LUIS, makeIntervention, page, SECRET, VISIT } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.interventions.${key}`, options)
const YEAR = new Date().getFullYear()

it('lists the interventions of the year for the team', async () => {
  const requests = mockApi('get', `${BASE}/interventions`, page([makeIntervention()]))
  renderSocial(<InterventionsPage />)

  const row = within(await screen.findByRole('row', { name: new RegExp(VISIT.name) }))
  expect(row.getByRole('link', { name: 'Pérez, Juana' })).toHaveAttribute(
    'href',
    '/d/social/people/sp-1',
  )
  expect(row.getByText(SECRET)).toBeInTheDocument()
  expect(row.getByText('12/03/2026')).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('year')).toBe(String(YEAR))
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/interventions.csv?year=${YEAR}`,
  )
})

it('shows a viewer that the description is reserved', async () => {
  mockApi('get', `${BASE}/interventions`, page([makeIntervention({ description: null })]))
  renderSocial(<InterventionsPage />, { level: 'viewer' })

  const row = within(await screen.findByRole('row', { name: new RegExp(VISIT.name) }))
  expect(row.getByText(t('social.reserved'))).toBeInTheDocument()
  expect(row.getByText('Lic. Marta Ruiz')).toBeInTheDocument()
  expect(screen.getByText(t('social.reservedHint'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('add') })).toBeNull()
  expect(
    screen.queryByRole('button', { name: label('editNamed', { name: VISIT.name }) }),
  ).toBeNull()
})

it('filters by type on the server', async () => {
  const requests = mockApi('get', `${BASE}/interventions`, page([makeIntervention()]))
  renderSocial(<InterventionsPage />)
  const user = userEvent.setup()

  await screen.findByRole('row', { name: new RegExp(VISIT.name) })
  await user.selectOptions(screen.getByLabelText(label('type')), INTERVIEW.id)

  await waitFor(() =>
    expect(requests.at(-1)?.url.searchParams.get('intervention_type_id')).toBe(INTERVIEW.id),
  )
})

it('records an intervention with a person found by search', async () => {
  mockApi('get', `${BASE}/interventions`, page([]))
  mockApi('get', `${BASE}/people`, page([LUIS]))
  const requests = mockApi('post', `${BASE}/interventions`, makeIntervention(), 201)
  renderSocial(<InterventionsPage />)
  const user = userEvent.setup()

  expect(await screen.findByText(label('emptyYear'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: t('social.people.find') }), 'gom')
  await user.click(
    await form.findByRole('button', {
      name: t('social.people.chooseNamed', { name: 'Gómez, Luis' }),
    }),
  )
  await user.selectOptions(form.getByLabelText(label('type')), INTERVIEW.id)
  await user.type(form.getByRole('textbox', { name: label('description') }), 'Primera consulta')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({
    intervention_type_id: INTERVIEW.id,
    person_id: 'sp-2',
    description: 'Primera consulta',
    performed_by: 'Ana Gómez',
  })
})

it('corrects an intervention', async () => {
  mockApi('get', `${BASE}/interventions`, page([makeIntervention()]))
  const requests = mockApi('patch', `${BASE}/interventions/i-1`, makeIntervention())
  renderSocial(<InterventionsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: VISIT.name }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByRole('textbox', { name: label('description') })).toHaveValue(SECRET)
  const performedBy = form.getByRole('textbox', { name: label('performedBy') })
  await user.clear(performedBy)
  await user.type(performedBy, 'Equipo')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    date: '2026-03-12',
    description: SECRET,
    performed_by: 'Equipo',
  })
})

it('reads another year from its first page, and closes the new intervention form', async () => {
  const requests = mockApi('get', `${BASE}/interventions`, page([makeIntervention()]))
  renderSocial(<InterventionsPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(t('app.year')), String(YEAR - 1))
  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(YEAR - 1)))
  await user.click(screen.getByRole('button', { name: label('add') }))

  await closeDialog(user)
})
