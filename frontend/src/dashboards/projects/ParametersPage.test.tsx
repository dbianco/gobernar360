import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { AXES, TERM } from './testData'
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

const param = (key: string, options = {}) => t(`projects.parameters.${key}`, options)

it.each([
  ['departments', '/departments/d-1', 'Obras Públicas', { name: 'Obras y Servicios' }],
  ['programs', '/programs/p-1', 'Plan de bacheo', { name: 'Obras y Servicios' }],
  ['owners', '/owners/w-1', 'María Pérez', { full_name: 'Obras y Servicios' }],
])('renames and deletes items of %s', async (tab, path, name, body) => {
  const renamed = mockApi('patch', `${BASE}${path}`, {}, 200)
  const deleted = mockApi('delete', `${BASE}${path}`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, tab)
  await user.click(await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }))
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, 'Obras y Servicios{Enter}')
  await waitFor(() => expect(renamed).toHaveLength(1))
  await user.click(screen.getByRole('button', { name: t('app.list.deleteNamed', { name }) }))

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(renamed[0].body).toEqual(body)
})

it('renames and deletes terms', async () => {
  const renamed = mockApi('patch', `${BASE}/terms/${TERM.id}`, TERM)
  const deleted = mockApi('delete', `${BASE}/terms/${TERM.id}`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('app.list.renameNamed', { name: TERM.name }) }),
  )
  const field = screen.getByRole('textbox', {
    name: t('app.list.renameNamed', { name: TERM.name }),
  })
  await user.clear(field)
  await user.type(field, 'Gestión actual{Enter}')
  await waitFor(() => expect(renamed[0]?.body).toEqual({ name: 'Gestión actual' }))
  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: TERM.name }) }),
  )

  await waitFor(() => expect(deleted).toHaveLength(1))
  // Terms are created with their years, not from the catalog's add field.
  expect(screen.queryByRole('textbox', { name: param('newItem') })).toBeNull()
})

it('adds, renames and deletes the axes and objectives of the selected term', async () => {
  const addedAxis = mockApi('post', `${BASE}/axes`, {}, 201)
  const renamedAxis = mockApi('patch', `${BASE}/axes/a-1`, {})
  const deletedAxis = mockApi('delete', `${BASE}/axes/a-1`, null, 204)
  const renamedObjective = mockApi('patch', `${BASE}/objectives/o-1`, {})
  const deletedObjective = mockApi('delete', `${BASE}/objectives/o-1`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'axes')
  await user.type(await screen.findByRole('textbox', { name: param('newAxis') }), 'Ciudad verde')
  await user.keyboard('{Enter}')
  await waitFor(() =>
    expect(addedAxis[0]?.body).toEqual({ term_id: TERM.id, name: 'Ciudad verde' }),
  )

  await user.click(
    screen.getByRole('button', { name: t('app.list.renameNamed', { name: 'Ciudad inclusiva' }) }),
  )
  const axisField = screen.getByRole('textbox', {
    name: t('app.list.renameNamed', { name: 'Ciudad inclusiva' }),
  })
  await user.clear(axisField)
  await user.type(axisField, 'Ciudad para todos{Enter}')
  await waitFor(() => expect(renamedAxis[0]?.body).toEqual({ name: 'Ciudad para todos' }))
  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: 'Ciudad inclusiva' }) }),
  )
  await waitFor(() => expect(deletedAxis).toHaveLength(1))

  const objective = 'Reducir el déficit habitacional'
  await user.click(
    screen.getByRole('button', { name: t('app.list.renameNamed', { name: objective }) }),
  )
  const objectiveField = screen.getByRole('textbox', {
    name: t('app.list.renameNamed', { name: objective }),
  })
  await user.clear(objectiveField)
  await user.type(objectiveField, 'Viviendas dignas{Enter}')
  await waitFor(() => expect(renamedObjective[0]?.body).toEqual({ name: 'Viviendas dignas' }))
  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: objective }) }),
  )
  await waitFor(() => expect(deletedObjective).toHaveLength(1))
})

it('does not save a budget that did not change, and shows the saved ones', async () => {
  mockCatalogs()
  mockApi('get', `${BASE}/terms/:termId/budgets`, [{ year: 2024, total_amount: '950000000.00' }])
  const saved = mockApi('put', `${BASE}/terms/${TERM.id}/budgets`, {})
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  const input = await screen.findByLabelText(param('budgetFor', { year: 2024 }))
  await waitFor(() => expect(input).toHaveValue(950000000))
  await user.click(input)
  await user.tab()
  const empty = screen.getByLabelText(param('budgetFor', { year: 2025 }))
  await user.click(empty)
  await user.tab()

  expect(saved).toHaveLength(0)
  expect(screen.getByText(`${param('budgets')} · ${TERM.name}`)).toBeInTheDocument()
})

it('lets the admin pick which term to configure', async () => {
  const budgets = mockApi('get', `${BASE}/terms/:termId/budgets`, [])
  mockCatalogs()
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByRole('combobox', { name: t('projects.term.change') }),
    't-0',
  )

  expect(await screen.findByText(`${param('budgets')} · Gestión 2019-2023`)).toBeInTheDocument()
  expect(budgets.at(-1)?.url.pathname).toContain('/terms/t-0/budgets')
  expect(screen.getByLabelText(param('budgetFor', { year: 2019 }))).toBeInTheDocument()
})

it('asks for a term before axes can be defined', async () => {
  mockCatalogs([])
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  await openTab(user, 'axes')

  expect(await screen.findByText(param('noTerm'))).toBeInTheDocument()
  expect(screen.queryByRole('combobox', { name: t('projects.term.change') })).toBeNull()
})

it('shows why the axes or the budgets could not be loaded', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/terms/:termId/budgets`, 500, 'generic')
  mockApiError('get', `${BASE}/axes`, 500, 'generic')
  const user = userEvent.setup()

  await screen.findByRole('tab', { name: param('axes') })
  await openTab(user, 'axes')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('lets the admin close the error of a change', async () => {
  mockApiError('post', `${BASE}/departments`, 422, 'validation_error')
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'departments')
  await user.type(await screen.findByLabelText(param('newItem')), 'X{Enter}')
  const alert = await screen.findByText(t('errors.validation_error'))
  await user.click(within(alert.closest('[role="alert"]') as HTMLElement).getByRole('button'))

  await waitFor(() => expect(screen.queryByText(t('errors.validation_error'))).toBeNull())
})

it('keeps what was typed for a term the server refused', async () => {
  mockApiError('post', `${BASE}/terms`, 409, 'conflict')
  renderParameters()
  const user = userEvent.setup()

  const name = await screen.findByLabelText(t('projects.parameters.name'))
  await user.type(name, 'Gestión 2027-2031')
  await user.type(screen.getByLabelText(t('projects.parameters.startYear')), '2027')
  await user.type(screen.getByLabelText(t('projects.parameters.endYear')), '2031')
  await user.click(screen.getByRole('button', { name: t('projects.parameters.addTerm') }))

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
  expect(name).toHaveValue('Gestión 2027-2031')
})

it.each(['departments', 'programs', 'owners', 'axes', 'objectives'])(
  'says why %s cannot be loaded',
  async (catalog) => {
    renderParameters()
    mockApiError('get', `${BASE}/${catalog}`, 500, 'boom')
    // Axes and objectives are looked up when their tab opens; the rest, at once.
    if (['axes', 'objectives'].includes(catalog)) await openTab(userEvent.setup(), 'axes')

    expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  },
)

it.each([
  ['departments', 'departments'],
  ['programs', 'programs'],
  ['owners', 'owners'],
  ['axes', 'axes'],
  ['axes', 'objectives'],
])('shows the %s tab with nothing in it when there are no %s at all', async (tab, catalog) => {
  renderParameters()
  mockApi('get', `${BASE}/${catalog}`, null)
  const user = userEvent.setup()

  await openTab(user, tab)

  const add = t('projects.parameters.newItem')
  const axis = t('projects.parameters.newAxis')
  expect(await screen.findByLabelText(tab === 'axes' ? axis : add)).toBeInTheDocument()
  const rename = /^Renombrar/
  // With no objectives the axes are still there.
  expect(screen.queryAllByRole('button', { name: rename })).toHaveLength(
    catalog === 'objectives' ? AXES.length : 0,
  )
})
