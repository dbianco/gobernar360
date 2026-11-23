import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProjectsPage } from './ProjectsPage'
import { makeProject, TERM } from './testData'
import { BASE, renderProjects } from './testRender'

it('lists the projects of the current term', async () => {
  const requests = mockApi('get', `${BASE}/projects`, [makeProject({ progress: 35 })])
  renderProjects(<ProjectsPage />)

  const row = within(await screen.findByRole('row', { name: /Pavimentación/ }))

  expect(row.getByText('Obras Públicas')).toBeInTheDocument()
  expect(row.getByText('35 %')).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('term_id')).toBe(TERM.id)
})

it('hides the create button from viewers', async () => {
  mockApi('get', `${BASE}/projects`, [makeProject()])
  renderProjects(<ProjectsPage />, { level: 'viewer' })

  await screen.findByRole('row', { name: /Pavimentación/ })

  expect(screen.queryByRole('button', { name: t('projects.list.create') })).not.toBeInTheDocument()
})

it('offers the create button to editors', async () => {
  mockApi('get', `${BASE}/projects`, [])
  renderProjects(<ProjectsPage />, { level: 'editor' })

  expect(await screen.findByRole('button', { name: t('projects.list.create') })).toBeInTheDocument()
  expect(await screen.findByText(t('projects.list.empty'))).toBeInTheDocument()
})

it('shows a delayed badge for delayed projects', async () => {
  mockApi('get', `${BASE}/projects`, [makeProject({ effective_status: 'delayed' })])
  renderProjects(<ProjectsPage />)

  const row = within(await screen.findByRole('row', { name: /Pavimentación/ }))

  expect(row.getByText(t('projects.status.delayed'))).toBeInTheDocument()
})

it('filters the list by status', async () => {
  const requests = mockApi('get', `${BASE}/projects`, [])
  renderProjects(<ProjectsPage />)

  await userEvent
    .setup()
    .selectOptions(
      await screen.findByLabelText(t('projects.filters.status')),
      t('projects.status.delayed'),
    )

  await waitFor(() =>
    expect(requests[requests.length - 1].url.searchParams.get('status')).toBe('delayed'),
  )
})

it('searches the projects by name and pages them ten at a time', async () => {
  const projects = [
    makeProject({ id: 'pr-plaza', name: 'Renovación de la plaza' }),
    ...Array.from({ length: 11 }, (_, index) =>
      makeProject({ id: `pr-${index}`, name: `Obra ${String(index + 1).padStart(2, '0')}` }),
    ),
  ]
  mockApi('get', `${BASE}/projects`, projects)
  renderProjects(<ProjectsPage />)
  const user = userEvent.setup()

  expect(await screen.findByRole('link', { name: 'Obra 09' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Obra 10' })).toBeNull()
  expect(screen.getByText(t('app.pager.range', { from: 1, to: 10, total: 12 }))).toBeInTheDocument()

  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'renovacion')

  expect(screen.getByRole('link', { name: 'Renovación de la plaza' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Obra 01' })).toBeNull()
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), ' zzz')
  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
})

it('creates a project from the list, and closes the form on cancel and with Escape', async () => {
  mockApi('get', `${BASE}/projects`, [])
  const requests = mockApi('post', `${BASE}/projects`, makeProject(), 201)
  renderProjects(<ProjectsPage />)
  const user = userEvent.setup()
  const create = await screen.findByRole('button', { name: t('projects.list.create') })

  await user.click(create)
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  await user.click(create)
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(create)
  const form = within(await screen.findByRole('dialog'))
  await form.findByRole('option', { name: 'Ciudad segura' })
  await form.findByRole('option', { name: 'Salud' })
  await user.type(form.getByRole('textbox', { name: t('projects.form.name') }), 'Cloacas')
  await user.selectOptions(form.getByRole('combobox', { name: t('projects.form.axis') }), 'Ciudad segura')
  await user.selectOptions(
    form.getByRole('combobox', { name: t('projects.form.department') }),
    'Salud',
  )
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(requests[0].body).toMatchObject({ name: 'Cloacas' })
})

it('says why the projects cannot be loaded', async () => {
  mockApiError('get', `${BASE}/projects`, 500, 'boom')
  renderProjects(<ProjectsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('says why the filters cannot be offered', async () => {
  mockApi('get', `${BASE}/projects`, [])
  renderProjects(<ProjectsPage />)
  mockApiError('get', `${BASE}/owners`, 500, 'boom')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByLabelText(t('projects.filters.status'))).toBeNull()
})

it('drops a filter set back to all', async () => {
  const requests = mockApi('get', `${BASE}/projects`, [])
  renderProjects(<ProjectsPage />)
  const user = userEvent.setup()
  const status = await screen.findByLabelText(t('projects.filters.status'))

  await user.selectOptions(status, t('projects.status.delayed'))
  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('status')).toBe('delayed'))
  await user.selectOptions(status, t('app.all'))

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.has('status')).toBe(false))
})
