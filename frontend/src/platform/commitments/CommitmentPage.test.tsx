import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import { choosePerson } from '../../test/person'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { CommitmentPage } from './CommitmentPage'
import {
  ANA,
  ASSIGNED,
  DONE,
  EVERYTHING,
  HIDDEN,
  LEO,
  makeDetail,
  makeInformal,
  makeRow,
  NOTHING,
  OWNER,
  PLAZA,
  ZOE,
} from './testData'
import { renderCommitments } from './testRender'
import type { CommitmentDetail } from './types'

const URL = '/commitments/co-1'
const label = (key: string, options = {}) => t(`commitments.detail.${key}`, options)
const form = (key: string) => t(`commitments.form.${key}`)
const history = (key: string, options = {}) => t(`commitments.history.${key}`, options)

const routes = (
  <Routes>
    <Route path="/commitments/:id" element={<CommitmentPage />} />
    <Route path="/commitments" element={<p>every list</p>} />
  </Routes>
)

function renderCommitment(commitment: CommitmentDetail = makeDetail()) {
  mockApi('get', URL, commitment)
  renderCommitments(routes, URL)
  return userEvent.setup()
}

const informal = (overrides: Partial<CommitmentDetail> = {}) =>
  makeDetail({ ...makeInformal({ id: 'co-1', rights: EVERYTHING }), ...overrides })
const button = (name: string) => screen.findByRole('button', { name })
const dialog = async () => within(await screen.findByRole('dialog'))
const value = (key: string) => screen.getByText(label(key)).nextElementSibling?.textContent

it('shows what was agreed and everything that happened to it', async () => {
  renderCommitment(
    makeDetail({
      followers: [ANA, ZOE],
      history: [
        {
          id: 'h-3',
          at: '2026-11-18T13:30:00Z',
          author: 'Ana Gómez',
          note: '',
          changes: { state: ['open', 'done'], completed_on: [null, '2026-11-18'] },
        },
        {
          id: 'h-2',
          at: '2026-11-01T02:00:00Z',
          author: null,
          note: '',
          changes: {
            owner: ['Ana Gómez', 'Leo Paz'],
            due_date: ['2026-11-10', '2026-11-20'],
            description: ['Certificar', 'Certificar la obra'],
          },
        },
        { id: 'h-1', at: '2026-10-21T13:30:00Z', author: 'Leo Paz', note: 'Empecé.', changes: {} },
      ],
    }),
  )

  expect(await screen.findByRole('heading', { name: 'Certificar la obra' })).toBeInTheDocument()
  expect(screen.getByText(t('commitments.states.overdue'))).toBeInTheDocument()
  expect(screen.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  expect([value('owner'), value('dueDate'), value('followers')]).toEqual([
    'Leo Paz',
    '20/11/2026',
    'Ana Gómez, Zoe Ruiz',
  ])
  expect(screen.queryByText(label('completedOn'))).toBeNull()
  expect(screen.queryByText(label('creator'))).toBeNull()
  expect(screen.getByRole('link', { name: 'Reunión del 20/10/2026' })).toHaveAttribute(
    'href',
    '/d/cabinet/meetings/me-0',
  )
  expect(screen.getByRole('link', { name: 'Plaza central' })).toBeInTheDocument()
  const [done, changed, note] = screen.getAllByRole('listitem')
  expect(done).toHaveTextContent('Ana Gómez')
  expect(done).toHaveTextContent(
    history('change', {
      field: history('fields.state'),
      before: t('commitments.states.open'),
      after: t('commitments.states.done'),
    }),
  )
  expect(done).toHaveTextContent(
    history('change', {
      field: history('fields.completed_on'),
      before: t('app.none'),
      after: '18/11/2026',
    }),
  )
  // In Argentine time it was still October.
  expect(changed).toHaveTextContent(history('unknown'))
  expect(changed).toHaveTextContent('31/10/2026, 23:00')
  expect(changed).toHaveTextContent('Ana Gómez → Leo Paz')
  expect(changed).toHaveTextContent('10/11/2026 → 20/11/2026')
  expect(changed).toHaveTextContent('Compromiso: Certificar → Certificar la obra')
  expect(note).toHaveTextContent('Empecé.')
})

it('says who gave an informal one, and when it was delivered', async () => {
  renderCommitment(
    informal({ state: 'done', completed_on: '2026-11-19', followers: [], rights: NOTHING }),
  )

  await screen.findByRole('heading', { name: 'Enviar la nota' })
  expect([value('creator'), value('completedOn'), value('followers')]).toEqual([
    'Ana Gómez',
    '19/11/2026',
    '—',
  ])
  expect(screen.getByText(t('commitments.informal'))).toBeInTheDocument()
})

it('names only the dashboard of a meeting to whoever cannot open it', async () => {
  renderCommitment(makeDetail({ origin: null, subject: HIDDEN, rights: OWNER }))

  expect(await screen.findByText(t('cabinet.title'))).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Reunión/ })).toBeNull()
  expect(screen.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
})

it('is marked done on the day it was by whoever owes it, who does not drop it', async () => {
  const user = renderCommitment(makeDetail({ rights: OWNER }))
  const posts = mockApi('post', `${URL}/state`, makeDetail())

  await user.click(await button(label('markDone')))
  expect(screen.queryByRole('button', { name: label('drop') })).toBeNull()
  const box = await dialog()
  const day = box.getByLabelText(label('completedOn'))
  expect(day).toHaveValue('23/11/2026')
  fireEvent.change(day, { target: { value: '19/11/2026' } })
  await user.type(box.getByLabelText(label('note')), 'Firmado.')
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(posts[0].body).toEqual({ state: 'done', completed_on: '2026-11-19', note: 'Firmado.' })
})

it('is not delivered in the future', async () => {
  const user = renderCommitment()
  const posts = mockApi('post', `${URL}/state`, makeDetail())

  await user.click(await button(label('markDone')))
  const box = await dialog()
  fireEvent.change(box.getByLabelText(label('completedOn')), { target: { value: '24/11/2026' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  expect(await box.findByText(t('app.date.max', { date: '23/11/2026' }))).toBeInTheDocument()
  expect(posts).toHaveLength(0)
})

it('is dropped by whoever gave it, who does not say it is done', async () => {
  const user = renderCommitment(informal({ rights: { ...EVERYTHING, finish: false } }))
  const posts = mockApi('post', `${URL}/state`, makeDetail())

  await user.click(await button(label('drop')))
  expect(screen.queryByRole('button', { name: label('markDone') })).toBeNull()
  const box = await dialog()
  expect(box.queryByLabelText(label('completedOn'))).toBeNull()
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(posts[0]?.body).toEqual({ state: 'dropped', note: '' }))
})

it('says why its state could not be changed, and cancels', async () => {
  const user = renderCommitment()
  mockApiError('post', `${URL}/state`, 422, 'validation_error')

  await user.click(await button(label('drop')))
  const box = await dialog()
  await user.click(box.getByRole('button', { name: t('app.save') }))
  expect(await box.findByText(t('errors.validation_error'))).toBeInTheDocument()
  await user.click(box.getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it.each(['done', 'dropped'] as const)('is reopened when it is %s', async (state) => {
  const user = renderCommitment(makeDetail({ state }))
  const posts = mockApi('post', `${URL}/state`, makeDetail())

  await user.click(await button(label('reopen')))

  await waitFor(() => expect(posts[0]?.body).toEqual({ state: 'open' }))
  for (const name of [label('markDone'), label('drop'), t('app.edit')]) {
    expect(screen.queryByRole('button', { name })).toBeNull()
  }
})

it('says why it could not be reopened', async () => {
  const user = renderCommitment(makeDetail({ state: 'done' }))
  mockApiError('post', `${URL}/state`, 403, 'forbidden')

  await user.click(await button(label('reopen')))

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})

it('is given to another by another day and attached to others, keeping what was agreed', async () => {
  const user = renderCommitment(makeDetail({ rights: OWNER, followers: [ZOE] }))
  const patches = mockApi('patch', URL, makeDetail())

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  expect(box.getByText(label('textOfMeeting'))).toBeInTheDocument()
  expect(box.getByLabelText(form('description'))).toBeDisabled()
  expect(box.queryByLabelText(t('subjects.about'))).toBeNull()
  await choosePerson(user, box.getByRole('combobox', { name: form('owner') }), ANA.full_name)
  fireEvent.change(box.getByLabelText(form('dueDate')), { target: { value: '15/12/2026' } })
  await choosePerson(user, box.getByRole('combobox', { name: form('followers') }), LEO.full_name)
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(patches[0].body).toEqual({
    owner_id: ANA.id,
    due_date: '2026-12-15',
    follower_ids: [ZOE.id, LEO.id],
  })
})

it('leaves for the lists when it was given to somebody else', async () => {
  const user = renderCommitment(informal({ owner: ANA, creator: LEO, rights: OWNER }))
  mockApi('patch', URL, informal({ rights: { ...NOTHING, see: false } }))

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  expect(box.getByText(label('textOfCreator'))).toBeInTheDocument()
  await choosePerson(user, box.getByRole('combobox', { name: form('owner') }), ZOE.full_name)
  await user.click(box.getByRole('button', { name: t('app.save') }))

  expect(await screen.findByText('every list')).toBeInTheDocument()
})

it('is corrected by whoever gave it', async () => {
  const user = renderCommitment(informal({ subject: PLAZA }))
  const patches = mockApi('patch', URL, informal())

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  await user.type(box.getByLabelText(form('description')), ' hoy')
  await user.selectOptions(box.getByLabelText(t('subjects.about')), '')
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(patches[0]?.body).toEqual({ description: 'Enviar la nota hoy', subject: null }))
})

it('keeps an owner and people attached who left, and a link that cannot be read', async () => {
  const GONE = { id: 'u-9', full_name: 'Ex Miembro' }
  const user = renderCommitment(informal({ owner: GONE, followers: [GONE], subject: HIDDEN }))
  const patches = mockApi('patch', URL, informal())
  mockApiError('get', '/members', 500, 'boom')

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  expect(box.getByRole('combobox', { name: form('owner') })).toHaveValue('Ex Miembro')
  expect(box.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  expect(await box.findByText(t('errors.generic'))).toBeInTheDocument()
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(patches[0]?.body).toEqual({}))
})

it('says why it could not be changed and closes the form with Escape', async () => {
  const user = renderCommitment()
  mockApiError('patch', URL, 409, 'commitment_finished')

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  await user.click(box.getByRole('button', { name: t('app.save') }))
  expect(await box.findByText(t('errors.commitment_finished'))).toBeInTheDocument()
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('takes progress notes', async () => {
  const user = renderCommitment(makeDetail({ rights: OWNER }))
  const posts = mockApi('post', `${URL}/notes`, makeDetail(), 201)
  const note = await screen.findByLabelText(label('newNote'))

  expect(screen.getByRole('button', { name: label('addNote') })).toBeDisabled()
  await user.type(note, 'Falta la firma.')
  await user.click(screen.getByRole('button', { name: label('addNote') }))

  await waitFor(() => expect(note).toHaveValue(''))
  expect(posts[0].body).toEqual({ note: 'Falta la firma.' })
})

it('keeps the note when it could not be added', async () => {
  const user = renderCommitment()
  mockApiError('post', `${URL}/notes`, 500, 'boom')

  await user.type(await screen.findByLabelText(label('newNote')), 'Falta.')
  await user.click(screen.getByRole('button', { name: label('addNote') }))

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.getByLabelText(label('newNote'))).toHaveValue('Falta.')
})

it('is only read by those attached', async () => {
  renderCommitment(makeDetail({ rights: NOTHING, subject: null }))

  expect(await screen.findByText(history('empty'))).toBeInTheDocument()
  expect(screen.queryAllByRole('button')).toHaveLength(0)
  expect(screen.queryByLabelText(label('newNote'))).toBeNull()
  expect(screen.queryByText(t('subjects.about'), { exact: false })).toBeNull()
})

it.each([
  ['one\'s own', { mine: [makeRow({ news: [ASSIGNED] })], others: [] }],
  ['another\'s', { mine: [], others: [makeRow({ news: [DONE] })] }],
])('reads the news of %s by being opened', async (_name, notifications) => {
  mockApi('get', '/notifications', notifications)
  const posts = mockApi('post', '/notifications/read', null, 204)
  renderCommitment()

  await waitFor(() => expect(posts[0]?.body).toEqual({ commitment_id: 'co-1' }))
})

it('does not mark what has no news, nor what others have', async () => {
  const requests = mockApi('get', '/notifications', {
    mine: [makeRow()],
    others: [makeRow({ id: 'co-9', news: [DONE] })],
  })
  const posts = mockApi('post', '/notifications/read', null, 204)
  renderCommitment()

  await screen.findByRole('heading', { name: 'Certificar la obra' })
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(posts).toHaveLength(0)
})

it('stays as news, and the page works, when it could not be marked', async () => {
  mockApi('get', '/notifications', { mine: [makeRow({ news: [ASSIGNED] })], others: [] })
  const posts = mockApiError('post', '/notifications/read', 500, 'boom')
  renderCommitment()

  await waitFor(() => expect(posts).toHaveLength(1))
  expect(screen.getByRole('heading', { name: 'Certificar la obra' })).toBeInTheDocument()
  expect(screen.queryByText(t('errors.generic'))).toBeNull()
})

it('says when it cannot be loaded', async () => {
  mockApiError('get', URL, 404, 'not_found')
  renderCommitments(routes, URL)

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: label('back') })).toHaveAttribute('href', '/commitments')
})
