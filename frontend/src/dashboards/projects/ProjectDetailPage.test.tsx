import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { answerConfirm } from '../../test/confirm'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProjectDetailPage } from './ProjectDetailPage'
import { makeMilestone, makeProject, OBJECTIVES, OWNERS, PROGRAMS } from './testData'
import { BASE, renderProjects } from './testRender'
import type { Project } from './types'

const PATH = '/d/projects/projects'
const form = (key: string) => t(`projects.form.${key}`)

function renderDetail(project: Project | null = makeProject(), level: AccessLevel = 'editor') {
  if (project) mockApi('get', `${BASE}/projects/${project.id}`, project)
  return renderProjects(
    <Routes>
      <Route path={`${PATH}/:id`} element={<ProjectDetailPage />} />
      <Route path={PATH} element={<p>project list</p>} />
    </Routes>,
    { level, route: `${PATH}/${project?.id ?? 'pr-1'}` },
  )
}

/** The value shown under a field's label. */
const field = (key: string) => screen.getByText(form(key)).nextElementSibling?.textContent

it('shows everything about the project', async () => {
  renderDetail(
    makeProject({
      name: 'Pavimentación de la calle San Martín',
      description: 'Cordón cuneta y carpeta asfáltica.',
      objective: OBJECTIVES[0],
      owner: OWNERS[0],
      program: PROGRAMS[0],
      priority: 'A+',
      year: 2025,
      start_date: '2025-03-01',
      end_date: '2025-12-15',
      planned_budget: '85000000.00',
      executed_budget: '41000000.50',
      progress: 35,
      sdgs: [9, 11],
      effective_status: 'delayed',
    }),
  )

  expect(
    await screen.findByRole('heading', { name: 'Pavimentación de la calle San Martín' }),
  ).toBeInTheDocument()
  expect(screen.getByText('Cordón cuneta y carpeta asfáltica.')).toBeInTheDocument()
  expect(screen.getByText(`${t('projects.filters.priority')} A+`)).toBeInTheDocument()
  expect(screen.getByText(`${t('projects.list.progress')}: 35 %`)).toBeInTheDocument()
  expect(screen.getByText(t('projects.status.delayed'))).toBeInTheDocument()
  expect(field('axis')).toBe('Ciudad inclusiva')
  expect(field('objective')).toBe('Reducir el déficit habitacional')
  expect(field('department')).toBe('Obras Públicas')
  expect(field('owner')).toBe('María Pérez')
  expect(field('program')).toBe('Plan de bacheo')
  expect(field('year')).toBe('2025')
  expect(field('startDate')).toBe('01/03/2025')
  expect(field('endDate')).toBe('15/12/2025')
  expect(field('plannedBudget')).toMatch(/^\$\s?85\.000\.000$/)
  expect(field('executedBudget')).toMatch(/^\$\s?41\.000\.001$/)
  expect(field('sdgs')).toBe(
    `${t('projects.sdgLabel', { number: 9, title: t('projects.sdg.9') })} · ${t(
      'projects.sdgLabel',
      { number: 11, title: t('projects.sdg.11') },
    )}`,
  )
})

it('says what the project lacks', async () => {
  renderDetail(makeProject())

  expect(await screen.findByText(t('projects.detail.noDescription'))).toBeInTheDocument()
  for (const key of ['objective', 'owner', 'program', 'startDate', 'endDate', 'sdgs']) {
    expect(field(key)).toBe(t('app.none'))
  }
})

it('shows its milestones', async () => {
  renderDetail(makeProject({ milestones: [makeMilestone({ name: 'Licitación adjudicada' })] }))

  expect(await screen.findByText('Licitación adjudicada')).toBeInTheDocument()
})

it('offers editing and deleting only to those who load data', async () => {
  renderDetail(makeProject(), 'viewer')

  await screen.findByRole('heading', { name: 'Pavimentación' })

  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
  expect(screen.queryByRole('button', { name: t('app.delete') })).toBeNull()
})

it('opens the project form to edit it, and closes it on cancel', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const dialog = await screen.findByRole('dialog', { name: form('editTitle') })
  expect(within(dialog).getByRole('textbox', { name: form('name') })).toHaveValue('Pavimentación')
  await user.click(within(dialog).getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('deletes the project after confirming and goes back to the list', async () => {
  const deleted = mockApi('delete', `${BASE}/projects/pr-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  const question = await answerConfirm(user, true)

  expect(question).toContain(t('projects.detail.deleteConfirm', { name: 'Pavimentación' }))
  expect(await screen.findByText('project list')).toBeInTheDocument()
  expect(deleted).toHaveLength(1)
})

it('keeps the project when the deletion is cancelled', async () => {
  const deleted = mockApi('delete', `${BASE}/projects/pr-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  await answerConfirm(user, false)

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(deleted).toHaveLength(0)
  expect(screen.getByRole('heading', { name: 'Pavimentación' })).toBeInTheDocument()
})

it('says why a deletion failed and stays on the project', async () => {
  mockApiError('delete', `${BASE}/projects/pr-1`, 409, 'in_use')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  expect(screen.queryByText('project list')).toBeNull()
})

it('shows an error when the project cannot be loaded', async () => {
  mockApiError('get', `${BASE}/projects/pr-1`, 404, 'not_found')
  renderDetail(null)

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('projects.detail.back') })).toHaveAttribute(
    'href',
    PATH,
  )
})

it('saves the edited project and closes the form, which Escape also closes', async () => {
  const saved = mockApi('patch', `${BASE}/projects/pr-1`, makeProject())
  renderDetail(makeProject({ objective: OBJECTIVES[0] }))
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  await screen.findByRole('dialog', { name: form('editTitle') })
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: t('app.edit') }))
  const dialog = within(await screen.findByRole('dialog', { name: form('editTitle') }))
  await dialog.findByRole('option', { name: OBJECTIVES[0].name })
  await user.selectOptions(dialog.getByRole('combobox', { name: form('objective') }), '')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(saved[0].body).toMatchObject({ objective_id: null })
})
