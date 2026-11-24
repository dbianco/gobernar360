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
      name: t('app.list.deleteNamed', { name: 'Obras Públicas' }),
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
  const requests = mockApi(
    'post',
    `${BASE}/objectives`,
    { id: 'o-3', axis_id: 'a-2', name: 'x' },
    201,
  )
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
  expect(screen.queryByText(t('app.list.empty'))).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: t('projects.parameters.addTerm') }),
  ).not.toBeInTheDocument()
})

const rename = async (user: ReturnType<typeof userEvent.setup>, name: string, newName: string) => {
  await user.click(await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }))
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, `${newName}{Enter}`)
}
const remove = async (user: ReturnType<typeof userEvent.setup>, name: string) =>
  user.click(await screen.findByRole('button', { name: t('app.list.deleteNamed', { name }) }))

it('renames and deletes catalog items', async () => {
  const renamed = mockApi('patch', `${BASE}/programs/p-1`, {})
  const deleted = mockApi('delete', `${BASE}/owners/w-1`, null, 204)
  const ownerRenamed = mockApi('patch', `${BASE}/owners/w-1`, {})
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'programs')
  await rename(user, 'Plan de bacheo', 'Bacheo 2025')
  await openTab(user, 'owners')
  await rename(user, 'María Pérez', 'María E. Pérez')
  await remove(user, 'María Pérez')

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(renamed[0].body).toEqual({ name: 'Bacheo 2025' })
  expect(ownerRenamed[0].body).toEqual({ full_name: 'María E. Pérez' })
})

it('renames and deletes terms, axes and objectives', async () => {
  const termRenamed = mockApi('patch', `${BASE}/terms/${TERM.id}`, {})
  const termDeleted = mockApi('delete', `${BASE}/terms/${TERM.id}`, null, 204)
  const axisRenamed = mockApi('patch', `${BASE}/axes/a-1`, {})
  const axisDeleted = mockApi('delete', `${BASE}/axes/a-1`, null, 204)
  const objectiveRenamed = mockApi('patch', `${BASE}/objectives/o-1`, {})
  const objectiveDeleted = mockApi('delete', `${BASE}/objectives/o-1`, null, 204)
  const axisAdded = mockApi('post', `${BASE}/axes`, {}, 201)
  renderParameters()
  const user = userEvent.setup()

  await rename(user, TERM.name, 'Gestión actual')
  await remove(user, TERM.name)
  await openTab(user, 'axes')
  await rename(user, 'Ciudad inclusiva', 'Ciudad para todos')
  await remove(user, 'Ciudad inclusiva')
  await rename(user, 'Reducir el déficit habitacional', 'Viviendas')
  await remove(user, 'Reducir el déficit habitacional')
  await user.type(
    screen.getByRole('textbox', { name: t('projects.parameters.newAxis') }),
    'Ciudad verde{Enter}',
  )

  await waitFor(() => expect(axisAdded).toHaveLength(1))
  expect(termRenamed[0].body).toEqual({ name: 'Gestión actual' })
  expect(termDeleted).toHaveLength(1)
  expect(axisRenamed[0].body).toEqual({ name: 'Ciudad para todos' })
  expect(axisDeleted).toHaveLength(1)
  expect(objectiveRenamed[0].body).toEqual({ name: 'Viviendas' })
  expect(objectiveDeleted).toHaveLength(1)
  expect(axisAdded[0].body).toEqual({ term_id: TERM.id, name: 'Ciudad verde' })
})

it('switches to another term', async () => {
  renderParameters()
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByRole('combobox', { name: t('projects.term.change') }),
    'Gestión 2019-2023',
  )

  expect(
    await screen.findByText(`${t('projects.parameters.budgets')} · Gestión 2019-2023`),
  ).toBeInTheDocument()
  expect(
    screen.getByLabelText(t('projects.parameters.budgetFor', { year: 2019 })),
  ).toBeInTheDocument()
})

it('does not save a budget left as it was', async () => {
  const requests = mockApi('put', `${BASE}/terms/${TERM.id}/budgets`, {})
  mockCatalogs()
  mockApi('get', `${BASE}/terms/:termId/budgets`, [{ year: 2024, total_amount: '100.00' }])
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  const input = await screen.findByDisplayValue('100.00')
  await user.click(input)
  await user.tab()
  await user.clear(input)
  await user.tab()

  expect(requests).toHaveLength(0)
})

it('explains an empty term list and reports budgets and axes that fail to load', async () => {
  mockCatalogs([])
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  await openTab(user, 'axes')

  expect(await screen.findByText(t('projects.parameters.noTerm'))).toBeInTheDocument()
})

it('reports budgets and axes that fail to load', async () => {
  mockCatalogs()
  mockApiError('get', `${BASE}/terms/:termId/budgets`, 500, 'generic')
  mockApiError('get', `${BASE}/axes`, 500, 'generic')
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  await openTab(user, 'axes')
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
