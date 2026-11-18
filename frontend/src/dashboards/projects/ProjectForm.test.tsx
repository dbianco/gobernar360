import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProjectForm } from './ProjectForm'
import { makeProject, TERM } from './testData'
import { BASE, renderProjects } from './testRender'

const label = (key: string) => t(`projects.form.${key}`)

/** The catalogs load after the form appears; wait until their options exist. */
const catalogsLoaded = async () => {
  await screen.findByRole('option', { name: 'Ciudad segura' })
  await screen.findByRole('option', { name: 'Salud' })
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await catalogsLoaded()
  await user.type(await screen.findByRole('textbox', { name: label('name') }), 'Cloacas barrio norte')
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
