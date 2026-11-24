import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
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
})

it('is read-only for viewers', async () => {
  const project = makeProject({ milestones: [makeMilestone()] })
  renderProjects(<MilestonesPanel project={project} canEdit={false} />)

  await screen.findByRole('row', { name: /Licitación/ })

  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

it('deletes a milestone', async () => {
  const milestone = makeMilestone()
  const requests = mockApi('delete', `${BASE}/milestones/${milestone.id}`, null, 204)
  renderProjects(<MilestonesPanel project={makeProject({ milestones: [milestone] })} canEdit />)

  await userEvent.click(
    await screen.findByRole('button', {
      name: t('projects.milestones.deleteNamed', { name: milestone.name }),
    }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})
