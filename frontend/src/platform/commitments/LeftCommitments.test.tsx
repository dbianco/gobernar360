import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { choosePerson } from '../../test/person'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { LeftCommitments } from './LeftCommitments'
import { ANA, LEO, ZOE } from './testData'
import { renderCommitments } from './testRender'
import type { LeftCommitment, LeftCommitments as Left } from './types'

const label = (key: string, options = {}) => t(`commitments.left.${key}`, options)
const makeLeft = (overrides: Partial<LeftCommitment> = {}): LeftCommitment => ({
  id: 'co-1',
  description: 'Certificar la obra',
  owner: LEO,
  due_date: '2026-11-20',
  source: 'cabinet',
  can_reassign: true,
  ...overrides,
})

function renderLeft(left: Left) {
  const current = { left }
  mockApi('get', '/admin/left-commitments', () => current.left as never)
  mockApi('get', '/members', [ANA, ZOE])
  renderCommitments(<LeftCommitments />)
  return { user: userEvent.setup(), current }
}

const reassign = (name: string) =>
  screen.findByRole('button', { name: label('reassignNamed', { name }) })

it('gives what somebody who left owed to somebody else', async () => {
  const { user, current } = renderLeft({ commitments: [makeLeft()], hidden: 0 })
  const saved = mockApi('patch', '/commitments/co-1', () => {
    current.left = { commitments: [], hidden: 0 }
    return {}
  })
  const button = await reassign('Certificar la obra')
  expect(button).toBeDisabled()
  expect(
    screen.getByText(
      `Certificar la obra · ${t('commitments.owed', { owner: LEO.full_name, date: '20/11/2026' })}`,
    ),
  ).toBeInTheDocument()

  await choosePerson(
    user,
    screen.getByRole('combobox', { name: label('newOwner', { name: 'Certificar la obra' }) }),
    ZOE.full_name,
  )
  await user.click(button)

  await waitFor(() => expect(saved[0]?.body).toEqual({ owner_id: ZOE.id }))
  await waitFor(() => expect(screen.queryByText(label('title'))).toBeNull())
})

it('says why it could not be given', async () => {
  const { user } = renderLeft({ commitments: [makeLeft()], hidden: 0 })
  mockApiError('patch', '/commitments/co-1', 422, 'invalid_reference')
  await reassign('Certificar la obra')

  await choosePerson(user, screen.getByRole('combobox'), ANA.full_name)
  await user.click(await reassign('Certificar la obra'))

  expect(await screen.findByText(t('errors.invalid_reference'))).toBeInTheDocument()
})

it('lists those it may only read about, and how many more there are', async () => {
  renderLeft({ commitments: [makeLeft({ can_reassign: false })], hidden: 2 })

  const list = within(await screen.findByRole('list', { name: label('title') }))
  expect(list.getByText(/Certificar la obra/)).toBeInTheDocument()
  expect(list.queryByRole('button')).toBeNull()
  expect(screen.getByText(label('hidden', { count: 2 }))).toBeInTheDocument()
})

it('says how many there are when it may see none', async () => {
  renderLeft({ commitments: [], hidden: 1 })

  expect(await screen.findByText(label('hidden', { count: 1 }))).toBeInTheDocument()
  expect(screen.queryByRole('list')).toBeNull()
})

it('is not there when nobody left anything', async () => {
  const asked = mockApi('get', '/admin/left-commitments', { commitments: [], hidden: 0 })
  renderCommitments(<LeftCommitments />)

  await waitFor(() => expect(asked).toHaveLength(1))
  expect(screen.queryByText(label('title'))).toBeNull()
})

it('says why it cannot be known', async () => {
  mockApiError('get', '/admin/left-commitments', 403, 'forbidden')
  renderCommitments(<LeftCommitments />)

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})
