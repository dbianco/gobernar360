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

it('opens and closes the form to create a project', async () => {
  mockApi('get', `${BASE}/projects`, [makeProject()])
  renderProjects(<ProjectsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('projects.list.create') }))
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: t('projects.list.create') }))
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('reports projects that cannot be loaded', async () => {
  mockApiError('get', `${BASE}/projects`, 500, 'generic')
  renderProjects(<ProjectsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
