import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ComplaintDetailPage } from './ComplaintDetailPage'
import { LAMP, LIGHTS, makeClock, makeDetail, NORTH, POTHOLE, TIMELINE, WORKS } from './testData'
import { BASE, renderComplaints } from './testRender'
import type { ComplaintDetail, ResidentNotice, TimelineEvent } from './types'

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

const message = () => t('complaints.actions.messageToResident')

it('writes the resident a message apart from the internal note', async () => {
  const moves = mockApi('post', `${URL}/transitions`, makeDetail(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: move('resolved') }))
  const dialog = within(await screen.findByRole('dialog'))
  const field = dialog.getByRole('textbox', { name: message() })
  expect(field).not.toBeRequired()
  expect(dialog.getByText(t('complaints.actions.messageHint'))).toBeInTheDocument()
  expect(
    dialog.getByText(t('complaints.actions.messageLeft', { count: 500 })),
  ).toBeInTheDocument()
  await user.type(dialog.getByRole('textbox', { name: t('complaints.actions.note') }), 'Interna')
  await user.type(field, 'Ya funciona')
  expect(
    dialog.getByText(t('complaints.actions.messageLeft', { count: 489 })),
  ).toBeInTheDocument()
  await user.click(dialog.getByRole('button', { name: move('resolved') }))

  await waitFor(() => expect(moves).toHaveLength(1))
  expect(moves[0].body).toEqual({
    to_state: 'resolved',
    note: 'Interna',
    message_to_resident: 'Ya funciona',
  })
})

it('offers the message when rejecting too', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: move('rejected') }))

  expect(
    within(await screen.findByRole('dialog')).getByRole('textbox', { name: message() }),
  ).toBeInTheDocument()
})

it('offers no message when there is nobody to read it', async () => {
  const moves = mockApi('post', `${URL}/transitions`, makeDetail(), 201)
  renderDetail(makeDetail({ person: null }))
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: move('resolved') }))
  const dialog = within(await screen.findByRole('dialog'))
  expect(dialog.queryByRole('textbox', { name: message() })).toBeNull()
  await user.click(dialog.getByRole('button', { name: move('resolved') }))

  await waitFor(() => expect(moves[0]?.body).toEqual({ to_state: 'resolved', note: '' }))
})

const notice = (key: string) => t(`complaints.notices.${key}`)
const makeNotice = (overrides: Partial<ResidentNotice> = {}): ResidentNotice => ({
  id: 'no-1',
  kind: 'complaint_resolved',
  channel: 'cidi',
  state: 'handed_over',
  created_at: '2026-03-04T12:00:00Z',
  handed_over_at: '2026-03-04T15:30:00Z',
  ...overrides,
})
const panel = async () => within(await screen.findByRole('region', { name: notice('title') }))

it('says what the resident was told, without claiming anything else', async () => {
  renderDetail(makeDetail({ notices: [makeNotice()] }))

  const shown = await panel()
  expect(shown.getByText('Entregado a CiDi')).toBeInTheDocument()
  expect(shown.getByText(notice('kinds.complaint_resolved'))).toBeInTheDocument()
  expect(shown.getByText('04/03/2026 12:30')).toBeInTheDocument()
  expect(shown.getByText(notice('cidiHelp'))).toBeInTheDocument()
})

it.each([
  ['Enviado por correo', makeNotice({ channel: 'email' })],
  ['En cola', makeNotice({ state: 'queued', handed_over_at: null })],
  ['Falló', makeNotice({ state: 'failed', handed_over_at: null })],
  ['Sin medio para avisar', makeNotice({ state: 'no_channel', handed_over_at: null })],
])('says "%s" in words', async (words, told) => {
  renderDetail(makeDetail({ notices: [told] }))

  const shown = await panel()
  expect(shown.getByText(words)).toBeInTheDocument()
  expect(shown.queryByText(notice('cidiHelp'))).toBeNull()
  expect(shown.queryAllByText(notice('noChannelHelp'))).toHaveLength(
    told.state === 'no_channel' ? 1 : 0,
  )
  expect(
    shown.getByText(told.handed_over_at ? '04/03/2026 12:30' : '04/03/2026 09:00'),
  ).toBeInTheDocument()
})

it('says when the resident was told nothing yet', async () => {
  renderDetail()

  expect((await panel()).getByText(notice('none'))).toBeInTheDocument()
})

it('shows the notices to nobody who does not get them, nor of an anonymous complaint', async () => {
  renderDetail(makeDetail({ notices: null }), 'viewer')
  await screen.findByRole('region', { name: detail('timeline') })

  expect(screen.queryByRole('region', { name: notice('title') })).toBeNull()
})

it('has nobody to tell about an anonymous complaint', async () => {
  renderDetail(makeDetail({ person: null }))
  await screen.findByRole('region', { name: detail('timeline') })

  expect(screen.queryByRole('region', { name: notice('title') })).toBeNull()
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

it('tells every kind of step apart in the history', async () => {
  const step = (id: string, overrides: Partial<TimelineEvent>): TimelineEvent => ({
    ...TIMELINE[1],
    id,
    from_state: null,
    to_state: null,
    ...overrides,
  })
  renderDetail(
    makeDetail({
      timeline: [
        step('ev-a', { kind: 'created', to_state: 'received', to_area: null }),
        step('ev-b', { kind: 'reassigned', from_area: LIGHTS, to_area: WORKS, note: 'Poste' }),
        step('ev-c', { kind: 'retyped', from_type: LAMP, to_type: POTHOLE }),
        step('ev-d', { kind: 'comment', note: 'Llamó el vecino' }),
        step('ev-e', { kind: 'transition', from_state: null, to_state: 'assigned' }),
      ],
    }),
  )
  const history = within(await screen.findByRole('region', { name: detail('timeline') }))

  expect(history.getByText(/^Recibido y derivado a/)).toBeInTheDocument()
  expect(history.getByText('Reasignado de Alumbrado Público a Obras Públicas')).toBeInTheDocument()
  expect(history.getByText('Tipo cambiado de Luminaria apagada a Bache')).toBeInTheDocument()
  expect(history.getByText(t('complaints.timeline.comment'))).toBeInTheDocument()
  expect(history.getByText('Llamó el vecino')).toBeInTheDocument()
  expect(history.getByText('→ Asignado')).toBeInTheDocument()
})

it('adds a note and closes dialogs without acting', async () => {
  const notes = mockApi('post', `${URL}/comments`, makeDetail(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('complaints.actions.comment') }))
  let dialog = within(await screen.findByRole('dialog'))
  await user.type(dialog.getByRole('textbox', { name: t('complaints.actions.note') }), 'Llamó')
  await user.click(dialog.getByRole('button', { name: t('complaints.actions.comment') }))
  await waitFor(() => expect(notes).toHaveLength(1))
  expect(notes[0].body).toEqual({ note: 'Llamó' })

  for (const open of [
    move('waiting'),
    t('complaints.actions.reassign'),
    t('complaints.actions.edit'),
  ]) {
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: open }))
    dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: t('app.cancel') }))
  }
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('corrects zone and description too', async () => {
  const sent = mockApi('patch', URL, makeDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('complaints.actions.edit') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.selectOptions(dialog.getByLabelText(t('complaints.form.zone')), NORTH.id)
  const description = dialog.getByRole('textbox', { name: t('complaints.form.description') })
  await user.clear(description)
  await user.type(description, 'Sigue apagada')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(sent).toHaveLength(1))
  expect(sent[0].body).toMatchObject({ zone_id: NORTH.id, description: 'Sigue apagada' })
})

it('reports a complaint that cannot be loaded', async () => {
  mockApiError('get', URL, 404, 'not_found')
  renderComplaints(
    <Routes>
      <Route path="/d/complaints/complaints/:id" element={<ComplaintDetailPage />} />
    </Routes>,
    { route: '/d/complaints/complaints/co-1' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})

it('reassigns to the area chosen and shows an anonymous complaint', async () => {
  const sent = mockApi('post', `${URL}/assignment`, makeDetail(), 201)
  renderDetail(makeDetail({ person: null }))
  mockApi('get', `${BASE}/areas`, [LIGHTS, WORKS, { id: 'ar-3', name: 'Zoonosis' }])
  const user = userEvent.setup()

  expect(await screen.findByText(detail('anonymous'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('complaints.actions.reassign') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.selectOptions(dialog.getByLabelText(t('complaints.actions.newArea')), 'ar-3')
  await user.click(dialog.getByRole('button', { name: t('complaints.actions.reassign') }))

  await waitFor(() => expect(sent).toHaveLength(1))
  expect(sent[0].body).toEqual({ area_id: 'ar-3', note: '' })
})

it('shows why a correction was refused', async () => {
  mockApiError('patch', URL, 409, 'case_not_open')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('complaints.actions.edit') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  expect(await dialog.findByText(t('errors.case_not_open'))).toBeInTheDocument()
})

it('writes a step whose area or type no longer has a name', async () => {
  const step = (id: string, overrides: Partial<TimelineEvent>): TimelineEvent => ({
    ...TIMELINE[1],
    id,
    ...overrides,
  })
  renderDetail(
    makeDetail({
      timeline: [
        step('ev-x', { kind: 'reassigned', from_area: null, to_area: null }),
        step('ev-y', { kind: 'retyped', from_type: null, to_type: null }),
      ],
    }),
  )
  const history = within(await screen.findByRole('region', { name: detail('timeline') }))

  expect(history.getByText(/^Reasignado de/)).toBeInTheDocument()
  expect(history.getByText(/^Tipo cambiado de/)).toBeInTheDocument()
})

it('opens its forms even when what they offer cannot be loaded', async () => {
  renderDetail()
  for (const list of ['areas', 'types', 'zones']) mockApiError('get', `${BASE}/${list}`, 500, 'boom')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('complaints.actions.reassign') }))
  expect(
    within(await screen.findByRole('dialog')).getByLabelText(t('complaints.actions.newArea')),
  ).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  await user.click(screen.getByRole('button', { name: t('complaints.actions.edit') }))
  expect(await screen.findByRole('dialog')).toBeInTheDocument()
})
