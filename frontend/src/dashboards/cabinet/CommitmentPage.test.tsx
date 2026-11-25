import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { CommitmentPage } from './CommitmentPage'
import { ANA, HIDDEN, LEO, makeCommitmentDetail } from './testData'
import { BASE, renderCabinet } from './testRender'
import type { CommitmentDetail } from './types'

const URL = `${BASE}/commitments/co-1`
const label = (key: string, options = {}) => t(`cabinet.commitment.${key}`, options)
const history = (key: string, options = {}) => t(`cabinet.history.${key}`, options)

function renderCommitment(
  commitment: CommitmentDetail = makeCommitmentDetail(),
  level: AccessLevel = 'editor',
) {
  mockApi('get', URL, commitment)
  renderCabinet(
    <Routes>
      <Route path="/d/cabinet/commitments/:id" element={<CommitmentPage />} />
    </Routes>,
    { level, route: '/d/cabinet/commitments/co-1' },
  )
  return userEvent.setup()
}

const button = (name: string) => screen.findByRole('button', { name })
const dialog = async () => within(await screen.findByRole('dialog'))

it('shows what was agreed and everything that happened to it', async () => {
  renderCommitment(
    makeCommitmentDetail({
      history: [
        {
          id: 'h-3',
          at: '2026-11-18T13:30:00Z',
          author: 'Ana Gómez',
          note: '',
          changes: {
            state: ['open', 'done'],
            completed_on: [null, '2026-11-18'],
          },
        },
        {
          id: 'h-2',
          at: '2026-11-01T02:00:00Z',
          author: null,
          note: '',
          changes: { owner: ['Ana Gómez', 'Leo Paz'], due_date: ['2026-11-10', '2026-11-20'] },
        },
        { id: 'h-1', at: '2026-10-21T13:30:00Z', author: 'Leo Paz', note: 'Empecé.', changes: {} },
      ],
    }),
  )

  expect(await screen.findByRole('heading', { name: 'Certificar la obra' })).toBeInTheDocument()
  expect(screen.getByText(t('cabinet.states.overdue'))).toBeInTheDocument()
  expect(screen.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '20/10/2026' })).toHaveAttribute(
    'href',
    '/d/cabinet/meetings/me-0',
  )
  expect(screen.getByRole('link', { name: 'Plaza central' })).toBeInTheDocument()
  const [done, changed, note] = screen.getAllByRole('listitem')
  expect(done).toHaveTextContent('Ana Gómez')
  expect(done).toHaveTextContent(
    history('change', {
      field: history('fields.state'),
      before: t('cabinet.states.open'),
      after: t('cabinet.states.done'),
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
  expect(note).toHaveTextContent('Empecé.')
})

it('marks it done on the day it was', async () => {
  const user = renderCommitment()
  const posts = mockApi('post', `${URL}/state`, makeCommitmentDetail())

  await user.click(await button(label('markDone')))
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
  const posts = mockApi('post', `${URL}/state`, makeCommitmentDetail())

  await user.click(await button(label('markDone')))
  const box = await dialog()
  fireEvent.change(box.getByLabelText(label('completedOn')), { target: { value: '24/11/2026' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  expect(await box.findByText(t('app.date.max', { date: '23/11/2026' }))).toBeInTheDocument()
  expect(posts).toHaveLength(0)
})

it('drops it, without a date', async () => {
  const user = renderCommitment(makeCommitmentDetail({ state: 'open' }))
  const posts = mockApi('post', `${URL}/state`, makeCommitmentDetail())

  await user.click(await button(label('drop')))
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

it.each(['done', 'dropped'] as const)('reopens one that is %s', async (state) => {
  const user = renderCommitment(makeCommitmentDetail({ state }))
  const posts = mockApi('post', `${URL}/state`, makeCommitmentDetail())

  await user.click(await button(label('reopen')))

  await waitFor(() => expect(posts[0]?.body).toEqual({ state: 'open' }))
  expect(screen.queryByRole('button', { name: label('markDone') })).toBeNull()
  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
})

it('says why it could not be reopened', async () => {
  const user = renderCommitment(makeCommitmentDetail({ state: 'done' }))
  mockApiError('post', `${URL}/state`, 403, 'forbidden')

  await user.click(await button(label('reopen')))

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})

it('gives it to someone else by another day, keeping what was agreed', async () => {
  const user = renderCommitment()
  const patches = mockApi('patch', URL, makeCommitmentDetail())

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  expect(box.getByText(label('textFixed'))).toBeInTheDocument()
  expect(box.getByLabelText(label('description'))).toBeDisabled()
  expect(box.queryByLabelText(t('subjects.about'))).toBeNull()
  await within(box.getByLabelText(label('owner'))).findByRole('option', { name: ANA.full_name })
  await user.selectOptions(box.getByLabelText(label('owner')), ANA.id)
  fireEvent.change(box.getByLabelText(label('dueDate')), { target: { value: '15/12/2026' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(patches[0].body).toEqual({ owner_id: ANA.id, due_date: '2026-12-15' })
})

it('keeps an owner who left the municipality and a link the person cannot read', async () => {
  const user = renderCommitment(
    makeCommitmentDetail({
      owner: { id: 'u-9', full_name: 'Ex Miembro' },
      subject: HIDDEN,
      meeting: { id: 'me-1', date: '2026-11-23', closed: false },
    }),
  )
  const patches = mockApi('patch', URL, makeCommitmentDetail())
  mockApiError('get', `${BASE}/members`, 500, 'boom')

  await user.click(await button(t('app.edit')))
  const box = await dialog()
  expect(box.getByLabelText(label('owner'))).toHaveDisplayValue('Ex Miembro')
  expect(box.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  expect(await box.findByText(t('errors.generic'))).toBeInTheDocument()
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(patches[0]?.body).toEqual({}))
})

it('closes the form with Escape', async () => {
  const user = renderCommitment()

  await user.click(await button(t('app.edit')))
  await dialog()
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('lets whoever owes it add progress notes though they only read', async () => {
  const user = renderCommitment(
    makeCommitmentDetail({ owner: { id: ANA.id, full_name: ANA.full_name } }),
    'viewer',
  )
  const posts = mockApi('post', `${URL}/notes`, makeCommitmentDetail(), 201)
  const note = await screen.findByLabelText(label('newNote'))

  expect(screen.getByRole('button', { name: label('addNote') })).toBeDisabled()
  await user.type(note, 'Falta la firma.')
  await user.click(screen.getByRole('button', { name: label('addNote') }))

  await waitFor(() => expect(note).toHaveValue(''))
  expect(posts[0].body).toEqual({ note: 'Falta la firma.' })
  expect(screen.queryByRole('button', { name: label('markDone') })).toBeNull()
})

it('keeps the note when it could not be added', async () => {
  const user = renderCommitment()
  mockApiError('post', `${URL}/notes`, 500, 'boom')

  await user.type(await screen.findByLabelText(label('newNote')), 'Falta.')
  await user.click(screen.getByRole('button', { name: label('addNote') }))

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.getByLabelText(label('newNote'))).toHaveValue('Falta.')
})

it('only shows it to other viewers', async () => {
  renderCommitment(makeCommitmentDetail({ owner: LEO, subject: null }), 'viewer')

  expect(await screen.findByText(history('empty'))).toBeInTheDocument()
  expect(screen.queryAllByRole('button')).toHaveLength(0)
  expect(screen.queryByLabelText(label('newNote'))).toBeNull()
  expect(screen.queryByText(t('subjects.about'), { exact: false })).toBeNull()
})

it('says when it cannot be loaded', async () => {
  mockApiError('get', URL, 404, 'not_found')
  renderCabinet(
    <Routes>
      <Route path="/d/cabinet/commitments/:id" element={<CommitmentPage />} />
    </Routes>,
    { route: '/d/cabinet/commitments/co-1' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})
