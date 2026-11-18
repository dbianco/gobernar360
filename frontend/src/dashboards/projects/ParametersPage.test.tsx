import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { TERM } from './testData'
import { BASE, mockCatalogs } from './testRender'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'

function renderParameters() {
  mockCatalogs()
  mockApi('get', `${BASE}/terms/:termId/budgets`, [])
  return renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
}

const openTab = async (user: ReturnType<typeof userEvent.setup>, key: string) =>
  user.click(await screen.findByRole('tab', { name: t(`projects.parameters.${key}`) }))

it('explains that a parameter in use cannot be deleted', async () => {
  mockApiError('delete', `${BASE}/departments/d-1`, 409, 'in_use')
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'departments')
  await user.click(
    await screen.findByRole('button', {
      name: t('projects.parameters.deleteNamed', { name: 'Obras Públicas' }),
    }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  expect(screen.getByText('Obras Públicas')).toBeInTheDocument()
})

it('adds a department', async () => {
  const requests = mockApi('post', `${BASE}/departments`, { id: 'd-3', name: 'Hacienda' }, 201)
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'departments')
  await user.type(await screen.findByLabelText(t('projects.parameters.newItem')), 'Hacienda')
  await user.click(screen.getByRole('button', { name: t('app.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'Hacienda' })
})

it('adds an owner using the full name field', async () => {
  const requests = mockApi('post', `${BASE}/owners`, { id: 'w-2', full_name: 'Juan Sosa' }, 201)
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'owners')
  await user.type(await screen.findByLabelText(t('projects.parameters.newItem')), 'Juan Sosa')
  await user.click(screen.getByRole('button', { name: t('app.add') }))

  await waitFor(() => expect(requests[0]?.body).toEqual({ full_name: 'Juan Sosa' }))
})

it('adds a term', async () => {
  const requests = mockApi('post', `${BASE}/terms`, TERM, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.type(await screen.findByLabelText(t('projects.parameters.name')), 'Gestión 2027-2031')
  await user.type(screen.getByLabelText(t('projects.parameters.startYear')), '2027')
  await user.type(screen.getByLabelText(t('projects.parameters.endYear')), '2031')
  await user.click(screen.getByRole('button', { name: t('projects.parameters.addTerm') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'Gestión 2027-2031', start_year: 2027, end_year: 2031 })
})

it('adds an objective to an axis of the current term', async () => {
  const requests = mockApi('post', `${BASE}/objectives`, { id: 'o-3', axis_id: 'a-2', name: 'x' }, 201)
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'axes')
  await user.type(
    await screen.findByLabelText(
      t('projects.parameters.newObjectiveFor', { name: 'Ciudad segura' }),
    ),
    'Más cámaras',
  )
  await user.keyboard('{Enter}')

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ axis_id: 'a-2', name: 'Más cámaras' })
})

it('sets the total budget of a year', async () => {
  const requests = mockApi('put', `${BASE}/terms/${TERM.id}/budgets`, {
    year: 2024,
    total_amount: '5000000.00',
  })
  renderParameters()
  const user = userEvent.setup()

  const input = await screen.findByLabelText(t('projects.parameters.budgetFor', { year: 2024 }))
  await user.type(input, '5000000')
  await user.tab()

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ year: 2024, total_amount: '5000000' })
})

it('shows an error instead of an empty catalog when loading fails', async () => {
  mockCatalogs()
  mockApiError('get', `${BASE}/terms`, 500, 'generic')
  mockApiError('get', `${BASE}/departments`, 500, 'generic')
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByText(t('projects.parameters.empty'))).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: t('projects.parameters.addTerm') }),
  ).not.toBeInTheDocument()
})
