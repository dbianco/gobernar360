import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { HeaderNotices } from './HeaderNotices'
import { ASSIGNED, makeRow, NOTIFICATIONS } from './testData'
import { renderCommitments } from './testRender'
import type { Notifications } from './types'

const label = (key: string, options = {}) => t(`notices.${key}`, options)

function renderHeader(notifications: Notifications) {
  mockApi('get', '/notifications', notifications)
  renderCommitments(<HeaderNotices />)
  return userEvent.setup()
}

it('counts what one owes and the news, and each leads to its list', async () => {
  renderHeader(NOTIFICATIONS)

  const mine = await screen.findByRole('link', {
    name: label('mineOverdueLabel', { count: 2, overdue: 1 }),
  })
  expect(mine).toHaveAttribute('href', '/notifications')
  expect(screen.getByRole('link', { name: label('newsLabel', { count: 2 }) })).toHaveAttribute(
    'href',
    '/notifications#others',
  )
  expect(screen.getAllByText('2')).toHaveLength(2)
})

it('shows what one owes on hover', async () => {
  const user = renderHeader({ mine: [makeRow()], others: [] })

  await user.hover(await screen.findByRole('link', { name: label('mineLabel', { count: 1 }) }))

  const title = await screen.findByText(label('sections.mine'))
  const card = within(title.parentElement!)
  expect(card.getByRole('link', { name: 'Certificar la obra' })).toHaveAttribute(
    'href',
    '/commitments/co-1',
  )
  expect(card.getByText('30/11/2026')).toBeInTheDocument()
  expect(card.getByText(t('commitments.states.open'))).toBeInTheDocument()
  expect(card.getByRole('link', { name: label('seeAll') })).toHaveAttribute(
    'href',
    '/notifications',
  )
})

it('shows the news on hover, of one\'s own and of others\'', async () => {
  const user = renderHeader(NOTIFICATIONS)

  await user.hover(await screen.findByRole('link', { name: label('newsLabel', { count: 2 }) }))

  const card = within((await screen.findByText(label('title'))).parentElement!)
  expect(card.getByText(label('kinds.assigned', { actor: 'Zoe Ruiz' }))).toBeInTheDocument()
  expect(card.getByText(label('kinds.done', { actor: 'Leo Paz' }))).toBeInTheDocument()
  // What has no news is not news.
  expect(card.queryByText('Pedir fotos')).toBeNull()
})

it('says when there is nothing', async () => {
  const user = renderHeader({ mine: [], others: [] })

  await user.hover(await screen.findByRole('link', { name: label('mineLabel', { count: 0 }) }))
  expect(await screen.findByText(label('empty.mine'))).toBeInTheDocument()
  await user.hover(screen.getByRole('link', { name: label('newsLabel', { count: 0 }) }))
  expect(await screen.findByText(label('noNews'))).toBeInTheDocument()
  // No count of zero.
  expect(screen.queryByText('0')).toBeNull()
})

it('previews five and says how many more there are', async () => {
  const rows = Array.from({ length: 120 }, (_, index) =>
    makeRow({ id: `co-${index}`, description: `Tarea ${index}`, news: [ASSIGNED] }),
  )
  const user = renderHeader({ mine: rows, others: [] })

  await user.hover(await screen.findByRole('link', { name: label('mineLabel', { count: 120 }) }))
  expect(await screen.findByText(label('more', { count: 115 }))).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: /^Tarea/ })).toHaveLength(5)
  expect(screen.getAllByText('99+')).toHaveLength(2)
})

it('looks again for news without reloading', async () => {
  const requests = mockApi('get', '/notifications', { mine: [], others: [] })
  renderCommitments(<HeaderNotices />)
  await screen.findByRole('link', { name: label('newsLabel', { count: 0 }) })
  await waitFor(() => expect(requests).toHaveLength(1))

  // Coming back to the window.
  window.dispatchEvent(new Event('visibilitychange'))
  document.dispatchEvent(new Event('visibilitychange'))

  await waitFor(() => expect(requests.length).toBeGreaterThan(1))
})
