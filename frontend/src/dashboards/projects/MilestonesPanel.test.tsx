import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { MilestonesPanel } from './MilestonesPanel'
import { makeMilestone, makeProject } from './testData'
import { BASE, renderProjects } from './testRender'

const today = () => {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

it('marks a milestone as completed', async () => {
  const milestone = makeMilestone()
  const requests = mockApi('patch', `${BASE}/milestones/${milestone.id}`, milestone)
  renderProjects(<MilestonesPanel project={makeProject({ milestones: [milestone] })} canEdit />)

  await userEvent
    .setup()
    .click(
      await screen.findByRole('button', {
        name: t('projects.milestones.completeNamed', { name: milestone.name }),
      }),
    )

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ completed_on: today() })
})

it('flags milestones in alert', async () => {
  const project = makeProject({
    milestones: [
      makeMilestone({ in_alert: true }),
      makeMilestone({ id: 'ms-2', name: 'Inicio de obra', due_date: '2025-09-01' }),
    ],
  })
  renderProjects(<MilestonesPanel project={project} canEdit />)

  const overdue = within(await screen.findByRole('row', { name: /Licitación/ }))
  const upcoming = within(screen.getByRole('row', { name: /Inicio de obra/ }))

  expect(overdue.getByText(t('projects.milestones.inAlert'))).toBeInTheDocument()
  expect(overdue.getByText('01/06/2025')).toBeInTheDocument()
  expect(upcoming.queryByText(t('projects.milestones.inAlert'))).not.toBeInTheDocument()
})

it('adds a milestone', async () => {
  const project = makeProject()
  const requests = mockApi('post', `${BASE}/projects/${project.id}/milestones`, makeMilestone(), 201)
  renderProjects(<MilestonesPanel project={project} canEdit />)
  const user = userEvent.setup()

  expect(await screen.findByText(t('projects.milestones.empty'))).toBeInTheDocument()
  await user.type(screen.getByLabelText(t('projects.milestones.name')), 'Licitación')
  await user.type(screen.getByLabelText(t('projects.milestones.dueDate')), '2025-06-01')
  await user.click(screen.getByRole('button', { name: t('projects.milestones.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'Licitación', due_date: '2025-06-01' })
  // Ready for the next one.
  await waitFor(() => expect(screen.getByLabelText(t('projects.milestones.name'))).toHaveValue(''))
  expect(screen.getByLabelText(t('projects.milestones.dueDate'))).toHaveValue('')
})

it('is read-only for viewers', async () => {
  const project = makeProject({ milestones: [makeMilestone()] })
  renderProjects(<MilestonesPanel project={project} canEdit={false} />)

  await screen.findByRole('row', { name: /Licitación/ })

  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

it('reopens a completed milestone and shows when it was completed', async () => {
  const milestone = makeMilestone({ completed_on: '2025-05-20' })
  const requests = mockApi('patch', `${BASE}/milestones/${milestone.id}`, milestone)
  renderProjects(<MilestonesPanel project={makeProject({ milestones: [milestone] })} canEdit />)
  const user = userEvent.setup()

  expect(
    await screen.findByText(t('projects.milestones.completedOn', { date: '20/05/2025' })),
  ).toBeInTheDocument()
  const reopen = screen.getByRole('button', {
    name: t('projects.milestones.reopenNamed', { name: milestone.name }),
  })
  expect(reopen).toHaveTextContent(t('projects.milestones.reopen'))
  await user.click(reopen)

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ completed_on: null })
})

it('deletes a milestone', async () => {
  const milestone = makeMilestone()
  const requests = mockApi('delete', `${BASE}/milestones/${milestone.id}`, null, 204)
  renderProjects(<MilestonesPanel project={makeProject({ milestones: [milestone] })} canEdit />)

  await userEvent.setup().click(
    await screen.findByRole('button', {
      name: t('projects.milestones.deleteNamed', { name: milestone.name }),
    }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('shows a pending milestone, an empty project, and why a change failed', async () => {
  mockApiError('post', `${BASE}/projects/pr-1/milestones`, 422, 'validation_error')
  renderProjects(<MilestonesPanel project={makeProject()} canEdit />)
  const user = userEvent.setup()

  expect(await screen.findByText(t('projects.milestones.empty'))).toBeInTheDocument()
  const name = screen.getByRole('textbox', { name: t('projects.milestones.name') })
  await user.type(name, 'Licitación')
  await user.type(screen.getByLabelText(t('projects.milestones.dueDate')), '2026-05-01')
  await user.click(screen.getByRole('button', { name: t('projects.milestones.add') }))

  expect(await screen.findByText(t('errors.validation_error'))).toBeInTheDocument()
  // What was typed stays, to be corrected.
  expect(name).toHaveValue('Licitación')
})

it('marks a milestone that is neither done nor overdue as pending', async () => {
  renderProjects(
    <MilestonesPanel project={makeProject({ milestones: [makeMilestone()] })} canEdit={false} />,
  )

  expect(await screen.findByText(t('projects.milestones.pending'))).toBeInTheDocument()
})
