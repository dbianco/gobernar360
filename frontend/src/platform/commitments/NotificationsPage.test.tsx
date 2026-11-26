import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { NotificationsPage } from './NotificationsPage'
import { DONE, makeRow, NOTIFICATIONS } from './testData'
import { renderCommitments } from './testRender'

const label = (key: string, options = {}) => t(`notices.${key}`, options)
const section = async (key: string) =>
  within(await screen.findByRole('region', { name: label(`sections.${key}`) }))

function renderPage(notifications = NOTIFICATIONS, route = '/notifications') {
  const requests = mockApi('get', '/notifications', notifications)
  renderCommitments(<NotificationsPage />, route)
  return { requests, user: userEvent.setup() }
}

it('lists one\'s open commitments and those of others one follows, with state, date and link', async () => {
  renderPage()

  const mine = await section('mine')
  const rows = (region: typeof mine) =>
    region
      .getAllByRole('row')
      .slice(1)
      .map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent))
  const read = label('read')
  expect(rows(mine)).toEqual([
    ['Señalizar', t('commitments.states.overdue'), '10/11/2026', ''],
    [
      'Certificar la obra',
      t('commitments.states.open'),
      '30/11/2026',
      `${label('kinds.assigned', { actor: 'Zoe Ruiz' })}${read}`,
    ],
  ])
  const others = await section('others')
  expect(rows(others)).toEqual([
    [
      'Enviar la nota',
      'Leo Paz',
      t('commitments.states.done'),
      '30/11/2026',
      `${label('kinds.done', { actor: 'Leo Paz' })}${read}`,
    ],
    ['Pedir fotos', 'Leo Paz', t('commitments.states.open'), '30/11/2026', ''],
  ])
  expect(mine.getByRole('link', { name: 'Señalizar' })).toHaveAttribute('href', '/commitments/co-3')
  expect(others.getByRole('link', { name: 'Enviar la nota' })).toHaveAttribute(
    'href',
    '/commitments/co-2',
  )
})

it('says when whoever owes one they gave is no longer a member', async () => {
  renderPage({
    mine: [],
    others: [
      makeRow({ news: [{ kind: 'owner_left', actor: 'Ana', at: '2026-11-23T12:00:00Z' }] }),
    ],
  })

  expect((await section('others')).getByText(label('kinds.owner_left'))).toBeInTheDocument()
})

it('marks one as read, and the list shows what is left', async () => {
  const { user } = renderPage()
  const posts = mockApi('post', '/notifications/read', null, 204)
  await section('others')
  mockApi('get', '/notifications', { mine: [], others: [] })

  await user.click(
    screen.getByRole('button', { name: label('readNamed', { name: 'Enviar la nota' }) }),
  )

  await waitFor(() => expect(posts[0]?.body).toEqual({ commitment_id: 'co-2' }))
  expect(await screen.findByText(label('empty.others'))).toBeInTheDocument()
  expect(screen.getByText(label('empty.mine'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('readAll') })).toBeNull()
})

it('marks everything as read', async () => {
  const { user } = renderPage()
  const posts = mockApi('post', '/notifications/read', null, 204)

  await user.click(await screen.findByRole('button', { name: label('readAll') }))

  await waitFor(() => expect(posts[0]?.body).toEqual({}))
})

it('says why it could not be marked', async () => {
  const { user } = renderPage()
  mockApiError('post', '/notifications/read', 500, 'boom')

  await user.click(await screen.findByRole('button', { name: label('readAll') }))

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('searches each list by what and who', async () => {
  const { user } = renderPage()
  const others = await section('others')

  await user.type(others.getByRole('searchbox'), 'fotos paz')
  expect(others.queryByText('Enviar la nota')).toBeNull()
  expect(others.getByText('Pedir fotos')).toBeInTheDocument()
  await user.type(others.getByRole('searchbox'), 'x')

  expect(others.getByText(t('app.noMatches'))).toBeInTheDocument()
  expect((await section('mine')).getByText('Señalizar')).toBeInTheDocument()
})

it('says somebody did it when their account is gone', async () => {
  renderPage({ mine: [], others: [makeRow({ news: [{ ...DONE, actor: null }] })] })

  expect(
    await screen.findByText(label('kinds.done', { actor: label('someone') })),
  ).toBeInTheDocument()
})

it('goes to the list asked for, or to the top', async () => {
  const scrolled = vi.spyOn(window.HTMLElement.prototype, 'scrollIntoView')
  const top = vi.spyOn(window, 'scrollTo')
  scrolled.mockClear()
  top.mockClear()
  renderPage(NOTIFICATIONS, '/notifications#others')
  await section('others')

  await waitFor(() => expect(scrolled).toHaveBeenCalledTimes(1))
  expect((scrolled.mock.contexts[0] as HTMLElement).id).toBe('others')
  expect(top).not.toHaveBeenCalled()
})

it('starts at the top when no list was asked for', async () => {
  const top = vi.spyOn(window, 'scrollTo')
  top.mockClear()
  renderPage()
  await section('mine')

  await waitFor(() => expect(top).toHaveBeenCalledWith(0, 0))
})

it('says when it cannot be loaded', async () => {
  mockApiError('get', '/notifications', 500, 'boom')
  renderCommitments(<NotificationsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
