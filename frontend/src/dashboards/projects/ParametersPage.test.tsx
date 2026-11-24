import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { AXES, OBJECTIVES, OLD_TERM, TERM } from './testData'
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
  expect(screen.queryByText(t('app.list.empty'))).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: t('projects.parameters.addTerm') }),
  ).not.toBeInTheDocument()
})

it("sets a target for one of the dashboard's indicators", async () => {
  mockApi('get', `${BASE}/targets`, [
    {
      key: 'projects.delayed',
      unit: null,
      higher_is_better: false,
      reconstructible: false,
      target: null,
    },
  ])
  const puts = mockApi('put', `${BASE}/targets/:year/projects.delayed`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'targets')
  const name = t('overview.indicators.projects.delayed')
  await user.type(
    await screen.findByRole('spinbutton', {
      name: t('indicators.targets.inputLabel', { name, year: new Date().getFullYear() }),
    }),
    '2{Enter}',
  )

  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ value: 2 })
  expect(puts[0].url.pathname).toContain(`/targets/${new Date().getFullYear()}/`)
})

const rename = async (
  user: ReturnType<typeof userEvent.setup>,
  name: string,
  newName: string,
) => {
  await user.click(
    await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }),
  )
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, `${newName}{Enter}`)
}

it('renames and deletes a term', async () => {
  const patches = mockApi('patch', `${BASE}/terms/${TERM.id}`, { ...TERM, name: 'Gestión actual' })
  const deletes = mockApi('delete', `${BASE}/terms/${TERM.id}`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await rename(user, TERM.name, 'Gestión actual')
  await waitFor(() => expect(patches).toHaveLength(1))
  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: TERM.name }) }),
  )

  await waitFor(() => expect(deletes).toHaveLength(1))
  expect(patches[0].body).toEqual({ name: 'Gestión actual' })
})

it('shows the budget already loaded for a year of the selected term', async () => {
  mockCatalogs()
  mockApi('get', `${BASE}/terms/:termId/budgets`, [
    { id: 'b-1', term_id: TERM.id, year: 2024, total_amount: '1500000.00' },
  ])
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })

  expect(
    await screen.findByLabelText(t('projects.parameters.budgetFor', { year: 2024 })),
  ).toHaveValue(1500000)
  expect(screen.getByLabelText(t('projects.parameters.budgetFor', { year: 2025 }))).toHaveValue(
    null,
  )
})

it('works on another term when one is chosen', async () => {
  renderParameters()
  // The axes are only read once their tab opens.
  const requests = mockApi('get', `${BASE}/axes`, [])
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByRole('combobox', { name: t('projects.term.change') }),
    OLD_TERM.id,
  )
  await openTab(user, 'axes')

  await waitFor(() =>
    expect(requests.at(-1)?.url.searchParams.get('term_id')).toBe(OLD_TERM.id),
  )
})

it('adds, renames and deletes axes and renames and deletes their objectives', async () => {
  const axes = {
    added: mockApi('post', `${BASE}/axes`, { id: 'a-3', term_id: TERM.id, name: 'Nuevo' }, 201),
    renamed: mockApi('patch', `${BASE}/axes/a-2`, AXES[1]),
    deleted: mockApi('delete', `${BASE}/axes/a-2`, null, 204),
  }
  const objectives = {
    renamed: mockApi('patch', `${BASE}/objectives/o-1`, OBJECTIVES[0]),
    deleted: mockApi('delete', `${BASE}/objectives/o-1`, null, 204),
  }
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'axes')
  await user.type(
    await screen.findByRole('textbox', { name: t('projects.parameters.newAxis') }),
    'Ciudad verde{Enter}',
  )
  await rename(user, 'Ciudad segura', 'Ciudad más segura')
  await user.click(
    await screen.findByRole('button', {
      name: t('app.list.deleteNamed', { name: 'Ciudad segura' }),
    }),
  )
  await rename(user, OBJECTIVES[0].name, 'Menos déficit')
  await user.click(
    await screen.findByRole('button', {
      name: t('app.list.deleteNamed', { name: OBJECTIVES[0].name }),
    }),
  )

  await waitFor(() => expect(objectives.deleted).toHaveLength(1))
  expect(axes.added[0].body).toEqual({ term_id: TERM.id, name: 'Ciudad verde' })
  expect(axes.renamed[0].body).toEqual({ name: 'Ciudad más segura' })
  expect(axes.deleted).toHaveLength(1)
  expect(objectives.renamed[0].body).toEqual({ name: 'Menos déficit' })
})

it('renames a department', async () => {
  const patches = mockApi('patch', `${BASE}/departments/d-2`, { id: 'd-2', name: 'Salud pública' })
  renderParameters()
  const user = userEvent.setup()

  await openTab(user, 'departments')
  await rename(user, 'Salud', 'Salud pública')

  await waitFor(() => expect(patches).toHaveLength(1))
  expect(patches[0].body).toEqual({ name: 'Salud pública' })
})

it('asks for a term before axes can be defined', async () => {
  mockCatalogs([])
  renderApp(<ParametersPage />, { me: makeMe({ dashboards: { projects: 'admin' } }) })
  const user = userEvent.setup()

  await openTab(user, 'axes')

  expect(await screen.findByText(t('projects.parameters.noTerm'))).toBeInTheDocument()
})

it('shows an error when the axes cannot be read', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/axes`, 500, 'generic')
  const user = userEvent.setup()

  await openTab(user, 'axes')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
