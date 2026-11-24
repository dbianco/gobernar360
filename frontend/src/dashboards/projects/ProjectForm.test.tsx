import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProjectForm } from './ProjectForm'
import { makeProject, OLD_TERM, TERM } from './testData'
import { BASE, renderProjects } from './testRender'

const label = (key: string) => t(`projects.form.${key}`)
const startsWith = (text: string) => new RegExp(`^${text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)

/** The catalogs load after the form appears; wait until their options exist. */
const catalogsLoaded = async () => {
  await screen.findByRole('option', { name: 'Ciudad segura' })
  await screen.findByRole('option', { name: 'Salud' })
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await catalogsLoaded()
  await user.type(
    await screen.findByRole('textbox', { name: label('name') }),
    'Cloacas barrio norte',
  )
  await user.selectOptions(screen.getByRole('combobox', { name: label('axis') }), 'Ciudad segura')
  await user.selectOptions(screen.getByRole('combobox', { name: label('department') }), 'Salud')
}

const optionNames = (select: HTMLElement) =>
  within(select)
    .getAllByRole('option')
    .map((option) => option.textContent)

it('limits objectives to the selected axis', async () => {
  renderProjects(<ProjectForm onSaved={vi.fn()} onCancel={vi.fn()} />)
  const user = userEvent.setup()
  await catalogsLoaded()

  await user.selectOptions(screen.getByRole('combobox', { name: label('axis') }), 'Ciudad segura')

  await screen.findByRole('option', { name: 'Más iluminación' })
  expect(optionNames(screen.getByRole('combobox', { name: label('objective') }))).toEqual([
    label('unassigned'),
    'Más iluminación',
  ])
})

it('submits the selected sdgs', async () => {
  const requests = mockApi('post', `${BASE}/projects`, makeProject(), 201)
  const onSaved = vi.fn()
  renderProjects(<ProjectForm onSaved={onSaved} onCancel={vi.fn()} />)
  const user = userEvent.setup()

  await fillRequired(user)
  await user.click(screen.getByRole('checkbox', { name: /^ODS 11:/ }))
  await user.click(screen.getByRole('checkbox', { name: /^ODS 3:/ }))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onSaved).toHaveBeenCalled())
  expect(requests[0].body).toMatchObject({
    term_id: TERM.id,
    name: 'Cloacas barrio norte',
    axis_id: 'a-2',
    department_id: 'd-2',
    objective_id: null,
    owner_id: null,
    priority: 'A',
    status: 'not_started',
    sdgs: [3, 11],
  })
})

it('shows the server validation message', async () => {
  mockApiError('post', `${BASE}/projects`, 422, 'validation_error')
  const onSaved = vi.fn()
  renderProjects(<ProjectForm onSaved={onSaved} onCancel={vi.fn()} />)
  const user = userEvent.setup()

  await fillRequired(user)
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  expect(await screen.findByText(t('errors.validation_error'))).toBeInTheDocument()
  expect(onSaved).not.toHaveBeenCalled()
})

it('edits an existing project with a partial update', async () => {
  const project = makeProject({ sdgs: [11], manual_progress: 20 })
  const requests = mockApi('patch', `${BASE}/projects/${project.id}`, project)
  renderProjects(<ProjectForm project={project} onSaved={vi.fn()} onCancel={vi.fn()} />)
  const user = userEvent.setup()

  const name = await screen.findByRole('textbox', { name: label('name') })
  expect(name).toHaveValue('Pavimentación')
  expect(await screen.findByRole('checkbox', { name: /^ODS 11:/ })).toBeChecked()
  await user.clear(name)
  await user.type(name, 'Pavimentación etapa 2')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ name: 'Pavimentación etapa 2', manual_progress: 20 })
  expect(requests[0].body).not.toHaveProperty('term_id')
})

it('hides manual progress once the project has milestones', async () => {
  const project = makeProject({
    milestones: [
      { id: 'ms-1', name: 'Hito', due_date: '2025-01-01', completed_on: null, in_alert: false },
    ],
  })
  renderProjects(<ProjectForm project={project} onSaved={vi.fn()} onCancel={vi.fn()} />)

  await screen.findByRole('textbox', { name: label('name') })

  expect(screen.queryByLabelText(label('manualProgress'))).not.toBeInTheDocument()
})

it("edits a project with the catalogs of the project's own term", async () => {
  // The project belongs to the old term while the newer one is selected on screen.
  const project = makeProject({ term_id: OLD_TERM.id, year: 2020 })
  const { catalogRequests } = renderProjects(
    <ProjectForm project={project} onSaved={vi.fn()} onCancel={vi.fn()} />,
  )

  await screen.findByRole('option', { name: '2020' })

  expect(catalogRequests.axes.at(-1)?.url.searchParams.get('term_id')).toBe(OLD_TERM.id)
  expect(screen.getByRole('combobox', { name: label('year') })).toHaveValue('2020')
})

it('sends every field the form has', async () => {
  const requests = mockApi('post', `${BASE}/projects`, makeProject(), 201)
  const onSaved = vi.fn()
  renderProjects(<ProjectForm onSaved={onSaved} onCancel={vi.fn()} />)
  // Many fields: type without the pause between keystrokes.
  const user = userEvent.setup({ delay: null })
  await fillRequired(user)
  const select = (key: string, option: string) =>
    user.selectOptions(screen.getByRole('combobox', { name: label(key) }), option)
  const field = (key: string) => screen.getByLabelText(startsWith(label(key)))

  await user.type(screen.getByRole('textbox', { name: label('description') }), 'Red cloacal')
  await screen.findByRole('option', { name: 'Más iluminación' })
  await select('objective', 'Más iluminación')
  await select('owner', 'María Pérez')
  await select('program', 'Plan de bacheo')
  // Optional choices can be left unassigned again.
  await select('program', label('unassigned'))
  await select('priority', 'B')
  await select('year', '2025')
  await select('status', 'in_progress')
  await user.type(field('startDate'), '2025-03-01')
  await user.type(field('endDate'), '2025-11-30')
  await user.clear(field('endDate'))
  await user.clear(field('plannedBudget'))
  await user.type(field('plannedBudget'), '1000')
  await user.clear(field('executedBudget'))
  await user.type(field('executedBudget'), '250')
  await user.type(field('manualProgress'), '30')
  await user.click(screen.getByRole('checkbox', { name: /^ODS 6:/ }))
  await user.click(screen.getByRole('checkbox', { name: /^ODS 9:/ }))
  await user.click(screen.getByRole('checkbox', { name: /^ODS 9:/ }))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onSaved).toHaveBeenCalled())
  expect(requests[0].body).toMatchObject({
    description: 'Red cloacal',
    objective_id: 'o-2',
    owner_id: 'w-1',
    program_id: null,
    priority: 'B',
    year: 2025,
    status: 'in_progress',
    start_date: '2025-03-01',
    end_date: null,
    planned_budget: '1000',
    executed_budget: '250',
    manual_progress: 30,
    sdgs: [6],
  })
})

it('clears a manual progress left empty and reports catalogs that failed to load', async () => {
  const requests = mockApi('patch', `${BASE}/projects/pr-1`, makeProject())
  renderProjects(
    <ProjectForm
      project={makeProject({ manual_progress: 40 })}
      onSaved={vi.fn()}
      onCancel={vi.fn()}
    />,
  )
  mockApiError('get', `${BASE}/programs`, 500, 'generic')
  const user = userEvent.setup()

  await user.clear(await screen.findByLabelText(startsWith(label('manualProgress'))))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ manual_progress: null })
})

it('leaves optional choices unassigned again', async () => {
  const requests = mockApi('patch', `${BASE}/projects/pr-1`, makeProject())
  renderProjects(
    <ProjectForm
      project={makeProject({
        objective: { id: 'o-1', name: 'x' },
        owner: { id: 'w-1', full_name: 'María Pérez' },
        start_date: '2024-01-10',
      })}
      onSaved={vi.fn()}
      onCancel={vi.fn()}
    />,
  )
  const user = userEvent.setup({ delay: null })
  await catalogsLoaded()

  await user.selectOptions(
    screen.getByRole('combobox', { name: label('objective') }),
    label('unassigned'),
  )
  await user.selectOptions(
    screen.getByRole('combobox', { name: label('owner') }),
    label('unassigned'),
  )
  await user.clear(screen.getByLabelText(startsWith(label('startDate'))))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ objective_id: null, owner_id: null, start_date: null })
})
