import { screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SubjectCommitments } from './SubjectCommitments'
import type { SubjectCommitment } from './types'

const URL = '/subjects/projects/project/pr-1/commitments'
const COMMITMENT: SubjectCommitment = {
  id: 'co-1',
  ref: 'pr-1',
  description: 'Certificar la obra',
  owner: 'Ana Gómez',
  due_date: '2026-11-30',
  overdue: false,
  times_postponed: 0,
  path: '/d/cabinet/commitments/co-1',
}
const show = () =>
  renderApp(
    <SubjectCommitments
      subject={{ dashboard_key: 'projects', kind: 'project', ref: 'pr-1' }}
    />,
    { me: makeMe() },
  )

it('lists what was agreed, who owes it, by when and how late it is', async () => {
  mockApi('get', URL, [
    { ...COMMITMENT, overdue: true, times_postponed: 2 },
    { ...COMMITMENT, id: 'co-2', description: 'Pedir presupuesto', times_postponed: 1 },
  ])
  show()

  const section = within(await screen.findByRole('region', { name: t('commitments.title') }))
  const [late, other] = section.getAllByRole('listitem').map((row) => within(row))
  expect(late.getByRole('link', { name: 'Certificar la obra' })).toHaveAttribute(
    'href',
    '/d/cabinet/commitments/co-1',
  )
  expect(
    late.getByText(t('commitments.owed', { owner: 'Ana Gómez', date: '30/11/2026' })),
  ).toBeInTheDocument()
  expect(late.getByText(t('commitments.overdue'))).toBeInTheDocument()
  expect(late.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  expect(other.queryByText(t('commitments.overdue'))).toBeNull()
  expect(other.getByText(t('commitments.postponed', { count: 1 }))).toBeInTheDocument()
})

it('shows nothing when there are none', async () => {
  const requests = mockApi('get', URL, [])
  show()

  await expect.poll(() => requests.length).toBe(1)
  expect(screen.queryByRole('region', { name: t('commitments.title') })).toBeNull()
})

it('says when they cannot be loaded', async () => {
  mockApiError('get', URL, 500, 'boom')
  show()

  expect(await screen.findByRole('alert')).toHaveTextContent(t('errors.generic'))
})
