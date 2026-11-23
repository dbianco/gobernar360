import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { answerConfirm } from '../../test/confirm'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { AssignmentsPanel } from './AssignmentsPanel'
import { CREDIT, makeAssignment, page, WORKSHOP } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string, options = {}) => t(`economic.assignments.${key}`, options)

function renderPanel(target = { actor_id: 'a-1' }) {
  const assignments = mockApi('get', `${BASE}/assignments`, page([makeAssignment()]))
  const view = renderEconomic(<AssignmentsPanel target={target} canEdit />)
  return { ...view, assignments }
}

it('asks for the most recent assignments of the target', async () => {
  const { assignments } = renderPanel({ actor_id: 'a-7' })

  expect(await screen.findByRole('row', { name: /Microcrédito productivo/ })).toBeInTheDocument()
  expect(assignments[0].url.searchParams.get('actor_id')).toBe('a-7')
  expect(assignments[0].url.searchParams.get('limit')).toBe('200')
})

it('says when the target received nothing, and when the list cannot be loaded', async () => {
  mockApi('get', `${BASE}/assignments`, page([]))
  const { unmount } = renderEconomic(<AssignmentsPanel target={{ actor_id: 'a-1' }} canEdit />)
  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  unmount()

  mockApiError('get', `${BASE}/assignments`, 500, 'boom')
  renderEconomic(<AssignmentsPanel target={{ actor_id: 'a-1' }} canEdit={false} />)
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('add') })).toBeNull()
})

it('keeps the form open and says why adding failed', async () => {
  renderPanel()
  mockApiError('post', `${BASE}/assignments`, 422, 'invalid_reference')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(await form.findByLabelText(label('tool')), CREDIT.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.invalid_reference'))).toBeInTheDocument()
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

it('says when no tool is meant for the target', async () => {
  renderPanel({ actor_id: 'a-1' })
  mockApi('get', `${BASE}/tools`, [WORKSHOP])
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  expect(await form.findByText(label('noTools'))).toBeInTheDocument()
  expect(form.getByRole('button', { name: t('app.save') })).toBeDisabled()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says why the tools cannot be loaded', async () => {
  renderPanel()
  mockApiError('get', `${BASE}/tools`, 500, 'boom')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  expect(await form.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('closes the edit form with Escape, and keeps an assignment whose deletion is not confirmed', async () => {
  const deleted = mockApi('delete', `${BASE}/assignments/as-1`, null, 204)
  renderPanel()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('editNamed', { name: 'Microcrédito productivo' }),
    }),
  )
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(
    screen.getByRole('button', { name: label('deleteNamed', { name: 'Microcrédito productivo' }) }),
  )
  await answerConfirm(user, false)
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(deleted).toHaveLength(0)
})

it('says why a deletion failed', async () => {
  renderPanel()
  mockApiError('delete', `${BASE}/assignments/as-1`, 409, 'in_use')
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteNamed', { name: 'Microcrédito productivo' }),
    }),
  )
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})
