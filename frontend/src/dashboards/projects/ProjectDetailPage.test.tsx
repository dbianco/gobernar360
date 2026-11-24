import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProjectDetailPage } from './ProjectDetailPage'
import { makeMilestone, makeProject, OBJECTIVES, OWNERS, PROGRAMS } from './testData'
import { BASE, renderProjects } from './testRender'

const PROJECT = makeProject({
  name: 'Plaza central',
  description: 'Renovación completa.\nCon juegos nuevos.',
  objective: OBJECTIVES[0],
  owner: OWNERS[0],
  program: PROGRAMS[0],
  priority: 'A+',
  start_date: '2025-03-01',
  end_date: '2025-12-15',
  planned_budget: '32000000.00',
  executed_budget: '12500000.00',
  progress: 40,
  sdgs: [11, 3],
  milestones: [makeMilestone({ name: 'Proyecto ejecutivo' })],
})

function renderDetail(level: AccessLevel = 'editor', project = PROJECT) {
  mockApi('get', `${BASE}/projects/${project.id}`, project)
  return renderProjects(
    <Routes>
      <Route path="/d/projects/projects/:id" element={<ProjectDetailPage />} />
      <Route path="/d/projects/projects" element={<p>Lista de proyectos</p>} />
    </Routes>,
    { level, route: `/d/projects/projects/${project.id}` },
  )
}

const field = (key: string) =>
  screen.getByText(t(`projects.form.${key}`)).parentElement as HTMLElement

afterEach(() => vi.restoreAllMocks())

it('shows everything about the project', async () => {
  renderDetail()

  expect(await screen.findByRole('heading', { name: 'Plaza central' })).toBeInTheDocument()
  expect(screen.getByText(`${t('projects.filters.priority')} A+`)).toBeInTheDocument()
  expect(screen.getByText(`${t('projects.list.progress')}: 40 %`)).toBeInTheDocument()
  expect(screen.getByText(/Renovación completa\./)).toBeInTheDocument()
  expect(field('objective')).toHaveTextContent('Reducir el déficit habitacional')
  expect(field('owner')).toHaveTextContent('María Pérez')
  expect(field('program')).toHaveTextContent('Plan de bacheo')
  expect(field('startDate')).toHaveTextContent('01/03/2025')
  expect(field('endDate')).toHaveTextContent('15/12/2025')
  expect(field('plannedBudget')).toHaveTextContent('32.000.000')
  expect(field('sdgs')).toHaveTextContent(
    t('projects.sdgLabel', { number: 11, title: t('projects.sdg.11') }),
  )
  expect(screen.getByText('Proyecto ejecutivo')).toBeInTheDocument()
})

it('says what is missing', async () => {
  renderDetail(
    'viewer',
    makeProject({ description: '', objective: null, owner: null, program: null, sdgs: [] }),
  )

  expect(await screen.findByText(t('projects.detail.noDescription'))).toBeInTheDocument()
  for (const key of ['objective', 'owner', 'program', 'sdgs']) {
    expect(field(key)).toHaveTextContent(t('app.none'))
  }
  // Viewers only read.
  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
  expect(screen.queryByRole('button', { name: t('app.delete') })).toBeNull()
})

it('opens the project form to edit it, and closes it', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const dialog = await screen.findByRole('dialog', { name: t('projects.form.editTitle') })
  expect(within(dialog).getByLabelText(t('projects.form.name'), { exact: false })).toHaveValue(
    'Plaza central',
  )
  await user.click(within(dialog).getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('deletes the project after confirming, and goes back to the list', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const deletes = mockApi('delete', `${BASE}/projects/${PROJECT.id}`, null, 204)
  renderDetail()

  await userEvent.click(await screen.findByRole('button', { name: t('app.delete') }))

  expect(await screen.findByText('Lista de proyectos')).toBeInTheDocument()
  expect(deletes).toHaveLength(1)
  expect(confirm).toHaveBeenCalledWith(
    t('projects.detail.deleteConfirm', { name: 'Plaza central' }),
  )
})

it('keeps the project when the deletion is not confirmed', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  const deletes = mockApi('delete', `${BASE}/projects/${PROJECT.id}`, null, 204)
  renderDetail()

  await userEvent.click(await screen.findByRole('button', { name: t('app.delete') }))

  expect(deletes).toHaveLength(0)
  expect(screen.getByRole('heading', { name: 'Plaza central' })).toBeInTheDocument()
})

it('says why a project cannot be deleted', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  mockApiError('delete', `${BASE}/projects/${PROJECT.id}`, 409, 'in_use')
  renderDetail()

  await userEvent.click(await screen.findByRole('button', { name: t('app.delete') }))

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('shows the error when the project cannot be read', async () => {
  mockApiError('get', `${BASE}/projects/missing`, 404, 'not_found')
  renderProjects(
    <Routes>
      <Route path="/d/projects/projects/:id" element={<ProjectDetailPage />} />
    </Routes>,
    { route: '/d/projects/projects/missing' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('projects.detail.back') })).toHaveAttribute(
    'href',
    '/d/projects/projects',
  )
})
