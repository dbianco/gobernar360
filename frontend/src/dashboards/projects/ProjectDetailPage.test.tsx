import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProjectDetailPage } from './ProjectDetailPage'
import { makeMilestone, makeProject, OBJECTIVES, OWNERS, PROGRAMS } from './testData'
import { BASE, renderProjects } from './testRender'
import type { Project } from './types'

afterEach(() => vi.restoreAllMocks())

function renderDetail(project: Project = makeProject(), level: AccessLevel = 'editor') {
  mockApi('get', `${BASE}/projects/pr-1`, project)
  return renderProjects(
    <Routes>
      <Route path="/d/projects/projects/:id" element={<ProjectDetailPage />} />
      <Route path="/d/projects/projects" element={<p>project list</p>} />
    </Routes>,
    { level, route: '/d/projects/projects/pr-1' },
  )
}

const field = (key: string) => t(`projects.form.${key}`)

it('shows every detail of the project', async () => {
  renderDetail(
    makeProject({
      description: 'Cordón cuneta y carpeta asfáltica.',
      objective: OBJECTIVES[0],
      owner: OWNERS[0],
      program: PROGRAMS[0],
      start_date: '2024-03-01',
      end_date: '2024-12-15',
      planned_budget: '1500000.00',
      progress: 40,
      sdgs: [9, 11],
      milestones: [makeMilestone()],
    }),
  )

  expect(await screen.findByRole('heading', { name: 'Pavimentación' })).toBeInTheDocument()
  expect(screen.getByText('Cordón cuneta y carpeta asfáltica.')).toBeInTheDocument()
  expect(screen.getByText(`${t('projects.list.progress')}: 40 %`)).toBeInTheDocument()
  expect(screen.getByText(OBJECTIVES[0].name)).toBeInTheDocument()
  expect(screen.getByText('María Pérez')).toBeInTheDocument()
  expect(screen.getByText('Plan de bacheo')).toBeInTheDocument()
  expect(screen.getByText('01/03/2024')).toBeInTheDocument()
  expect(screen.getByText('15/12/2024')).toBeInTheDocument()
  expect(screen.getByText(/1\.500\.000/)).toBeInTheDocument()
  expect(
    screen.getByText(
      `${t('projects.sdgLabel', { number: 9, title: t('projects.sdg.9') })} · ${t(
        'projects.sdgLabel',
        { number: 11, title: t('projects.sdg.11') },
      )}`,
    ),
  ).toBeInTheDocument()
  expect(screen.getByText('Licitación')).toBeInTheDocument()
})

it('marks what the project does not have', async () => {
  renderDetail()

  expect(await screen.findByText(t('projects.detail.noDescription'))).toBeInTheDocument()
  // Objective, owner, program and goals.
  expect(screen.getAllByText(t('app.none')).length).toBeGreaterThanOrEqual(4)
})

it('edits the project in a dialog and can cancel', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  expect(await screen.findByRole('dialog', { name: field('editTitle') })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('deletes the project after confirming and goes back to the list', async () => {
  const deleted = mockApi('delete', `${BASE}/projects/pr-1`, null, 204)
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))

  expect(await screen.findByText('project list')).toBeInTheDocument()
  expect(deleted).toHaveLength(1)
  expect(confirm).toHaveBeenCalledWith(
    t('projects.detail.deleteConfirm', { name: 'Pavimentación' }),
  )
})

it('keeps the project when the deletion is not confirmed or fails', async () => {
  const deleted = mockApiError('delete', `${BASE}/projects/pr-1`, 409, 'in_use')
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  expect(deleted).toHaveLength(0)
  confirm.mockReturnValue(true)
  await user.click(screen.getByRole('button', { name: t('app.delete') }))

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Pavimentación' })).toBeInTheDocument()
})

it('lets viewers read without editing', async () => {
  renderDetail(makeProject(), 'viewer')

  expect(await screen.findByRole('heading', { name: 'Pavimentación' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
  expect(screen.queryByRole('button', { name: t('app.delete') })).toBeNull()
})

it('reports a project that cannot be loaded', async () => {
  mockApiError('get', `${BASE}/projects/pr-1`, 404, 'not_found')
  renderProjects(
    <Routes>
      <Route path="/d/projects/projects/:id" element={<ProjectDetailPage />} />
    </Routes>,
    { route: '/d/projects/projects/pr-1' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})
