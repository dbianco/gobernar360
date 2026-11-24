import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ComplaintDetailPage } from './ComplaintDetailPage'
import { LAMP, makeClock, makeDetail, POTHOLE, WORKS } from './testData'
import { BASE, renderComplaints } from './testRender'
import type { ComplaintDetail } from './types'

const detail = (key: string, options = {}) => t(`complaints.detail.${key}`, options)
const move = (key: string) => t(`complaints.moves.${key}`)
const URL = `${BASE}/complaints/co-1`

function renderDetail(data: ComplaintDetail = makeDetail(), level: AccessLevel = 'editor') {
  mockApi('get', URL, data)
  return renderComplaints(
    <Routes>
      <Route path="/d/complaints/complaints/:id" element={<ComplaintDetailPage />} />
    </Routes>,
    { level, route: '/d/complaints/complaints/co-1' },
  )
}

it('shows the complaint, who made it, its clock and its history', async () => {
  renderDetail()

  expect(
    await screen.findByRole('heading', { name: detail('title', { number: 101 }) }),
  ).toBeInTheDocument()
  expect(screen.getByText(t('complaints.states.in_progress'))).toBeInTheDocument()
  expect(screen.getByText('Fernández, Lucía · DNI 33.123.456 · 3472 55-1234')).toBeInTheDocument()
  expect(screen.getByText('02/03/2026 09:30')).toBeInTheDocument()
  const clock = within(screen.getByRole('region', { name: detail('clock') }))
  expect(clock.getByText('3 días hábiles')).toBeInTheDocument()
  expect(clock.getByText('1 día hábil')).toBeInTheDocument()
  expect(clock.getByText('Quedan 2 días hábiles')).toBeInTheDocument()
  expect(clock.getByText('05/03/2026')).toBeInTheDocument()
  const history = within(screen.getByRole('region', { name: detail('timeline') }))
  expect(history.getByText('Recibido y derivado a Alumbrado Público')).toBeInTheDocument()
  expect(history.getByText('Asignado → En curso')).toBeInTheDocument()
  expect(history.getByText('Cuadrilla en camino')).toBeInTheDocument()
  expect(
    history.getByText(`${t('complaints.timeline.unknownUser')} · 03/03/2026 11:15`),
  ).toBeInTheDocument()
})

it('offers only the moves the state allows: no closing what was never resolved', async () => {
  renderDetail()
  const actions = within(await screen.findByRole('region', { name: detail('actions') }))

  expect(actions.getByRole('button', { name: move('waiting') })).toBeInTheDocument()
  expect(actions.getByRole('button', { name: move('resolved') })).toBeInTheDocument()
  expect(actions.getByRole('button', { name: move('rejected') })).toBeInTheDocument()
  expect(actions.queryByRole('button', { name: move('closed') })).not.toBeInTheDocument()
  expect(actions.queryByRole('button', { name: move('reopened') })).not.toBeInTheDocument()
})

it('moves the complaint with a note', async () => {
  const moves = mockApi('post', `${URL}/transitions`, makeDetail(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: move('waiting') }))
  const dialog = within(await screen.findByRole('dialog'))
  expect(dialog.getByText(t('complaints.actions.waitingHint'))).toBeInTheDocument()
  await user.type(
    dialog.getByRole('textbox', { name: t('complaints.actions.note') }),
    'Pedimos la altura',
  )
  await user.click(dialog.getByRole('button', { name: move('waiting') }))

  await waitFor(() => expect(moves).toHaveLength(1))
  expect(moves[0].body).toEqual({ to_state: 'waiting', note: 'Pedimos la altura' })
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('asks why before rejecting', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: move('rejected') }))

  const note = within(await screen.findByRole('dialog')).getByRole('textbox', {
    name: t('complaints.actions.note'),
  })
  expect(note).toBeRequired()
})

it('shows why the API refused a move', async () => {
  mockApiError('post', `${URL}/transitions`, 409, 'invalid_transition')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: move('resolved') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.click(dialog.getByRole('button', { name: move('resolved') }))

  expect(await dialog.findByText(t('errors.invalid_transition'))).toBeInTheDocument()
})

it('reads a paused clock and offers to resume the work', async () => {
  renderDetail(
    makeDetail({
      state: 'waiting',
      moves: ['in_progress', 'rejected'],
      clock: makeClock({ paused: true }),
    }),
  )

  expect(await screen.findByText(detail('pausedHint'))).toBeInTheDocument()
  expect(screen.getAllByText(t('complaints.paused')).length).toBeGreaterThan(0)
  expect(screen.getByRole('button', { name: move('resume') })).toBeInTheDocument()
})

it('shows how long a resolved complaint took', async () => {
  renderDetail(
    makeDetail({
      state: 'closed',
      moves: [],
      clock: makeClock({
        used_days: 5,
        left_days: -2,
        status: 'overdue',
        resolved_on: '2026-03-09',
      }),
    }),
  )

  const clock = within(await screen.findByRole('region', { name: detail('clock') }))
  expect(clock.getByText('Resuelto en 5 días hábiles')).toBeInTheDocument()
  expect(clock.getByText('09/03/2026')).toBeInTheDocument()
  expect(clock.getByText(t('complaints.outcomes.overdue'))).toBeInTheDocument()
  // Finished: only a note can be added.
  const actions = within(screen.getByRole('region', { name: detail('actions') }))
  expect(actions.getAllByRole('button').map((button) => button.textContent)).toEqual([
    t('complaints.actions.comment'),
  ])
})

it('reassigns to another area', async () => {
  const sent = mockApi('post', `${URL}/assignment`, makeDetail(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('complaints.actions.reassign') }))
  const dialog = within(await screen.findByRole('dialog'))
  const areas = dialog.getByLabelText(t('complaints.actions.newArea'))
  expect(
    within(areas)
      .getAllByRole('option')
      .map((option) => option.textContent),
  ).toEqual([WORKS.name])
  await user.click(dialog.getByRole('button', { name: t('complaints.actions.reassign') }))

  await waitFor(() => expect(sent).toHaveLength(1))
  expect(sent[0].body).toEqual({ area_id: WORKS.id, note: '' })
})

it('corrects the type and address', async () => {
  const sent = mockApi('patch', URL, makeDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('complaints.actions.edit') }))
  const dialog = within(await screen.findByRole('dialog'))
  expect(dialog.getByLabelText(t('complaints.form.type'))).toHaveValue(LAMP.id)
  await user.selectOptions(dialog.getByLabelText(t('complaints.form.type')), POTHOLE.id)
  const address = dialog.getByRole('textbox', { name: t('complaints.form.address') })
  await user.clear(address)
  await user.type(address, 'Mitre 10')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(sent).toHaveLength(1))
  expect(sent[0].body).toMatchObject({ type_id: POTHOLE.id, address: 'Mitre 10' })
})

it('lets a viewer read but not act', async () => {
  renderDetail(makeDetail(), 'viewer')

  expect(
    await screen.findByRole('heading', { name: detail('title', { number: 101 }) }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: detail('actions') })).not.toBeInTheDocument()
  expect(screen.queryAllByRole('button', { name: /Marcar|Rechazar|Reasignar|nota/ })).toEqual([])
})
