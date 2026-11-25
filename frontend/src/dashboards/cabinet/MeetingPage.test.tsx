import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { answerConfirm } from '../../test/confirm'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { MeetingPage } from './MeetingPage'
import { HIDDEN, LEO, LIGHT_ITEM, makeCommitment, makeItem, makeMeeting, ZOE } from './testData'
import { BASE, renderCabinet } from './testRender'
import type { MeetingDetail } from './types'

const URL = `${BASE}/meetings/me-1`
const label = (key: string, options = {}) => t(`cabinet.meeting.${key}`, options)
const agenda = (key: string, options = {}) => t(`cabinet.agenda.${key}`, options)
const form = (key: string, options = {}) => t(`cabinet.commitment.${key}`, options)
const FERIA = { name: 'Feria del libro' }
const OCT = { name: 'Ambiental, octubre de 2026' }

function renderMeeting(meeting: MeetingDetail = makeMeeting(), level: AccessLevel = 'editor') {
  mockApi('get', URL, meeting)
  renderCabinet(
    <Routes>
      <Route path="/d/cabinet/meetings/:id" element={<MeetingPage />} />
      <Route path="/d/cabinet/meetings" element={<p>every meeting</p>} />
    </Routes>,
    { level, route: '/d/cabinet/meetings/me-1' },
  )
  return userEvent.setup()
}

const heading = () => screen.findByRole('heading', { name: label('title', { date: '23/11/2026' }) })
const section = (name: string) => screen.findByRole('region', { name })
const dialog = async () => within(await screen.findByRole('dialog'))

it('shows who came, what was carried over and the agenda', async () => {
  renderMeeting(
    makeMeeting({
      carried_over: [makeCommitment()],
      items: [
        makeItem({ carried: true, subject: HIDDEN, notes: 'Falta sede.' }),
        LIGHT_ITEM,
        makeItem({
          id: 'it-3',
          source: 'commitment',
          title: 'Pedir presupuesto',
          topic: makeCommitment({ id: 'co-5', description: 'Pedir presupuesto' }),
          discussed: true,
        }),
      ],
    }),
  )

  await heading()
  expect(screen.getByText(label('open'))).toBeInTheDocument()
  expect(screen.getByText('Ana Gómez, Leo Paz')).toBeInTheDocument()
  expect(screen.getByText('Ing. Funes')).toBeInTheDocument()
  const carried = within(await section(label('carriedOver')))
  expect(carried.getByRole('link', { name: 'Certificar la obra' })).toHaveAttribute(
    'href',
    '/d/cabinet/commitments/co-1',
  )
  expect(carried.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  const feria = within(await section('Feria del libro'))
  expect(feria.getByText('1. Feria del libro')).toBeInTheDocument()
  expect(feria.getByText(agenda('carried'))).toBeInTheDocument()
  expect(feria.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  const light = within(await section(OCT.name))
  expect(light.getByRole('link', { name: t('status.states.red') })).toBeInTheDocument()
  // Its name is not the person's to change.
  expect(light.queryByRole('button', { name: agenda('editNamed', OCT) })).toBeNull()
  const topic = within(await section('Pedir presupuesto'))
  expect(topic.getByText(t('cabinet.states.overdue'))).toBeInTheDocument()
  expect(
    topic.getByRole('link', { name: form('viewNamed', { name: 'Pedir presupuesto' }) }),
  ).toHaveAttribute('href', '/d/cabinet/commitments/co-5')
})

it('saves notes when leaving them, only if they changed', async () => {
  const user = renderMeeting()
  const items = mockApi('patch', `${BASE}/items/it-1`, makeMeeting())
  const meetings = mockApi('patch', URL, makeMeeting())
  const notes = await screen.findByRole('textbox', { name: agenda('notesOf', FERIA) })

  await user.click(notes)
  await user.tab()
  await user.type(notes, 'Se confirma.')
  await user.tab()
  await user.type(screen.getByRole('textbox', { name: label('notes') }), 'Fin.')
  await user.tab()

  await waitFor(() => expect(meetings).toHaveLength(1))
  expect(items.map((request) => request.body)).toEqual([{ notes: 'Se confirma.' }])
  expect(meetings[0].body).toEqual({ notes: 'Fin.' })
})

it('keeps the notes typed when saving fails, and follows those saved elsewhere', async () => {
  const user = renderMeeting()
  mockApiError('patch', `${BASE}/items/it-1`, 500, 'boom')
  const notes = await screen.findByRole('textbox', { name: agenda('notesOf', FERIA) })

  await user.type(notes, 'Se confirma.')
  await user.tab()
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(notes).toHaveValue('Se confirma.')

  // Another person wrote about the light; a change of ours brings it.
  mockApi(
    'get',
    URL,
    makeMeeting({ items: [makeItem(), { ...LIGHT_ITEM, notes: 'De otra persona' }] }),
  )
  mockApi('patch', `${BASE}/items/it-2`, makeMeeting())
  await user.click(screen.getByRole('checkbox', { name: agenda('discussedNamed', OCT) }))

  await waitFor(() =>
    expect(screen.getByRole('textbox', { name: agenda('notesOf', OCT) })).toHaveValue(
      'De otra persona',
    ),
  )
  expect(notes).toHaveValue('Se confirma.')
})

it('marks an item as discussed', async () => {
  const user = renderMeeting()
  const patches = mockApi('patch', `${BASE}/items/it-1`, makeMeeting())

  await user.click(await screen.findByRole('checkbox', { name: agenda('discussedNamed', FERIA) }))

  await waitFor(() => expect(patches[0]?.body).toEqual({ discussed: true }))
})

it('moves items', async () => {
  const user = renderMeeting()
  const puts = mockApi('put', `${URL}/items/order`, makeMeeting())

  const up = await screen.findByRole('button', { name: agenda('moveUp', FERIA) })
  expect(up).toBeDisabled()
  expect(screen.getByRole('button', { name: agenda('moveDown', OCT) })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: agenda('moveDown', FERIA) }))

  await waitFor(() => expect(puts[0]?.body).toEqual({ item_ids: ['it-2', 'it-1'] }))
})

it('adds an item linked to a record', async () => {
  const user = renderMeeting()
  const posts = mockApi('post', `${URL}/items`, makeMeeting(), 201)

  await user.click(await screen.findByRole('button', { name: agenda('add') }))
  const box = await dialog()
  await user.type(box.getByLabelText(agenda('itemTitle')), 'Obra')
  await box.findByRole('option', { name: /proyecto/ })
  await user.selectOptions(box.getByLabelText(t('subjects.about')), 'projects/project')
  await user.click(await box.findByRole('combobox', { name: t('subjects.which') }))
  await user.click(await screen.findByRole('option', { name: 'Plaza central' }))
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(posts[0].body).toEqual({
    title: 'Obra',
    subject: { dashboard_key: 'projects', kind: 'project', ref: 'pr-1' },
  })
})

it('renames an item without touching a link the person cannot read', async () => {
  const user = renderMeeting(makeMeeting({ items: [makeItem({ subject: HIDDEN })] }))
  const patches = mockApi('patch', `${BASE}/items/it-1`, makeMeeting())

  await user.click(await screen.findByRole('button', { name: agenda('editNamed', FERIA) }))
  const box = await dialog()
  expect(box.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  const title = box.getByLabelText(agenda('itemTitle'))
  await user.clear(title)
  await user.type(title, 'Feria')
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(patches[0]?.body).toEqual({ title: 'Feria' }))
})

it('keeps the item form open and says why it failed, and closes it on cancel', async () => {
  const user = renderMeeting()
  mockApiError('post', `${URL}/items`, 409, 'meeting_closed')

  await user.click(await screen.findByRole('button', { name: agenda('add') }))
  const box = await dialog()
  await user.type(box.getByLabelText(agenda('itemTitle')), 'Obra')
  await user.click(box.getByRole('button', { name: t('app.save') }))
  expect(await box.findByText(t('errors.meeting_closed'))).toBeInTheDocument()
  await user.click(box.getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('removes an item that produced nothing, after confirming', async () => {
  const user = renderMeeting(
    makeMeeting({ items: [makeItem(), { ...LIGHT_ITEM, commitments: [makeCommitment()] }] }),
  )
  const deletes = mockApi('delete', `${BASE}/items/it-1`, null, 204)
  const remove = () => screen.findByRole('button', { name: agenda('removeNamed', FERIA) })

  await user.click(await remove())
  await answerConfirm(user, false)
  expect(deletes).toHaveLength(0)
  await user.click(await remove())
  expect(await answerConfirm(user, true)).toContain(label('removeMessage', FERIA))

  await waitFor(() => expect(deletes).toHaveLength(1))
  expect(screen.queryByRole('button', { name: agenda('removeNamed', OCT) })).toBeNull()
})

it('records a commitment about what the item is about', async () => {
  const user = renderMeeting()
  const posts = mockApi('post', `${BASE}/items/it-2/commitments`, makeCommitment(), 201)

  await user.click(await screen.findByRole('button', { name: agenda('addCommitmentTo', OCT) }))
  const box = await dialog()
  const owner = box.getByLabelText(form('owner'))
  await within(owner).findByRole('option', { name: LEO.full_name })
  // Whoever could not follow it is told apart.
  expect(
    within(owner).getByRole('option', { name: form('noAccess', { name: ZOE.full_name }) }),
  ).toBeInTheDocument()
  await user.type(box.getByLabelText(form('description')), 'Reparar la balanza')
  await user.selectOptions(owner, LEO.id)
  fireEvent.change(box.getByLabelText(form('dueDate')), { target: { value: '2026-12-01' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(posts[0].body).toEqual({
    description: 'Reparar la balanza',
    owner_id: LEO.id,
    due_date: '2026-12-01',
    subject: { dashboard_key: 'environment', kind: 'month', ref: '2026-10' },
  })
})

it('starts a commitment from what the followed up one is about, or from nothing', async () => {
  const user = renderMeeting(
    makeMeeting({
      items: [
        makeItem(),
        makeItem({
          id: 'it-3',
          source: 'commitment',
          title: 'Certificar la obra',
          topic: makeCommitment(),
        }),
      ],
    }),
  )
  const name = { name: 'Certificar la obra' }

  await user.click(await screen.findByRole('button', { name: agenda('addCommitmentTo', name) }))
  let box = await dialog()
  expect(await box.findByRole('combobox', { name: t('subjects.which') })).toHaveValue(
    'Plaza central',
  )
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: agenda('addCommitmentTo', FERIA) }))
  box = await dialog()
  expect(box.getByLabelText(t('subjects.about'))).toHaveValue('')
})

it('says why a commitment could not be recorded and keeps what was typed', async () => {
  const user = renderMeeting()
  mockApiError('post', `${BASE}/items/it-1/commitments`, 422, 'invalid_reference')

  await user.click(await screen.findByRole('button', { name: agenda('addCommitmentTo', FERIA) }))
  const box = await dialog()
  await within(box.getByLabelText(form('owner'))).findByRole('option', { name: LEO.full_name })
  await user.type(box.getByLabelText(form('description')), 'Pedir sede')
  await user.selectOptions(box.getByLabelText(form('owner')), LEO.id)
  fireEvent.change(box.getByLabelText(form('dueDate')), { target: { value: '2026-12-01' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  expect(await box.findByText(t('errors.invalid_reference'))).toBeInTheDocument()
  expect(box.getByLabelText(form('description'))).toHaveValue('Pedir sede')
})

it('corrects and removes commitments while the meeting is open', async () => {
  const taken = makeCommitment({
    state: 'open',
    times_postponed: 0,
    meeting: { id: 'me-1', date: '2026-11-23', closed: false },
  })
  const user = renderMeeting(makeMeeting({ items: [makeItem({ commitments: [taken] })] }))
  const patches = mockApi('patch', `${BASE}/commitments/co-1`, taken)
  const deletes = mockApi('delete', `${BASE}/commitments/co-1`, null, 204)
  const name = { name: 'Certificar la obra' }

  await user.click(await screen.findByRole('button', { name: form('editNamed', name) }))
  const box = await dialog()
  await user.type(box.getByLabelText(form('description')), ' vial')
  await user.selectOptions(box.getByLabelText(t('subjects.about')), '')
  await user.click(box.getByRole('button', { name: t('app.save') }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  // Only what changed.
  expect(patches[0].body).toEqual({ description: 'Certificar la obra vial', subject: null })

  await user.click(screen.getByRole('button', { name: form('removeNamed', name) }))
  await answerConfirm(user, true)
  await waitFor(() => expect(deletes).toHaveLength(1))
  // With commitments taken it cannot be discarded.
  expect(screen.queryByRole('button', { name: label('discard') })).toBeNull()
})

it('corrects its date and people', async () => {
  const user = renderMeeting(
    makeMeeting({ attendees: [{ id: 'u-9', full_name: 'Ex Miembro' }] }),
  )
  const patches = mockApi('patch', URL, makeMeeting())

  await user.click(await screen.findByRole('button', { name: label('edit') }))
  const box = await dialog()
  // Someone who left the municipality is still in the list.
  expect(box.getAllByText('Ex Miembro').length).toBeGreaterThan(0)
  fireEvent.change(box.getByLabelText(label('date')), { target: { value: '2026-11-25' } })
  await user.click(box.getByRole('combobox', { name: label('attendees') }))
  await user.click(await screen.findByRole('option', { name: LEO.full_name }))
  await user.type(box.getByLabelText(label('guests')), ' y prensa')
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(patches[0].body).toEqual({
    date: '2026-11-25',
    attendee_ids: ['u-9', LEO.id],
    guests: 'Ing. Funes y prensa',
  })
})

it('says why its data could not be saved', async () => {
  const user = renderMeeting()
  mockApiError('patch', URL, 422, 'meeting_before_last')
  mockApiError('get', `${BASE}/members`, 500, 'boom')

  await user.click(await screen.findByRole('button', { name: label('edit') }))
  const box = await dialog()
  await user.click(box.getByRole('button', { name: t('app.save') }))

  expect(await box.findByText(t('errors.meeting_before_last'))).toBeInTheDocument()
  expect(await box.findByText(t('errors.generic'))).toBeInTheDocument()
  await user.click(box.getByRole('button', { name: t('app.cancel') }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('is closed after confirming', async () => {
  const user = renderMeeting()
  const closes = mockApi('post', `${URL}/close`, makeMeeting({ closed: true }))
  const close = () => screen.findByRole('button', { name: label('close') })

  await user.click(await close())
  await answerConfirm(user, false, label('closeTitle'))
  expect(closes).toHaveLength(0)
  await user.click(await close())
  expect(await answerConfirm(user, true, label('closeTitle'))).toContain(label('closeMessage'))

  await waitFor(() => expect(closes).toHaveLength(1))
})

it('saves what was being typed before closing, and does not close if that fails', async () => {
  const user = renderMeeting()
  const order: string[] = []
  mockApi('patch', `${BASE}/items/it-1`, () => {
    order.push('notes')
    return makeMeeting()
  })
  mockApi('post', `${URL}/close`, () => {
    order.push('close')
    return makeMeeting()
  })

  await user.type(await screen.findByRole('textbox', { name: agenda('notesOf', FERIA) }), 'A')
  await user.click(screen.getByRole('button', { name: label('close') }))
  await answerConfirm(user, true, label('closeTitle'))
  await waitFor(() => expect(order).toEqual(['notes', 'close']))

  mockApiError('patch', `${BASE}/items/it-1`, 500, 'boom')
  await user.type(screen.getByRole('textbox', { name: agenda('notesOf', FERIA) }), 'B')
  await user.click(screen.getByRole('button', { name: label('close') }))
  await answerConfirm(user, true, label('closeTitle'))

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(order).toEqual(['notes', 'close'])
})

it('is discarded after confirming, while it took no commitments', async () => {
  const user = renderMeeting()
  const deletes = mockApi('delete', URL, null, 204)
  const discard = () => screen.findByRole('button', { name: label('discard') })

  await user.click(await discard())
  await answerConfirm(user, false)
  expect(deletes).toHaveLength(0)
  await user.click(await discard())
  expect(await answerConfirm(user, true)).toContain(label('discardMessage'))

  expect(await screen.findByText('every meeting')).toBeInTheDocument()
  expect(deletes).toHaveLength(1)
})

it('stays where it is when discarding fails', async () => {
  const user = renderMeeting()
  mockApiError('delete', URL, 409, 'in_use')

  await user.click(await screen.findByRole('button', { name: label('discard') }))
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it.each([
  ['a closed meeting', true, 'editor'],
  ['an open meeting read by a viewer', false, 'viewer'],
] as const)('cannot change anything in %s', async (_name, closed, level) => {
  renderMeeting(
    makeMeeting({
      closed,
      closed_at: closed ? '2026-11-23T15:00:00Z' : null,
      notes: 'Cierre general',
      items: [
        makeItem({ notes: 'Se confirma.', discussed: true, commitments: [makeCommitment()] }),
        LIGHT_ITEM,
      ],
    }),
    level,
  )

  await heading()
  expect(screen.getByText('Cierre general')).toBeInTheDocument()
  expect(screen.getByText('Se confirma.')).toBeInTheDocument()
  expect(screen.getAllByText(agenda('notDiscussed'))).toHaveLength(1)
  expect(screen.queryAllByRole('button')).toHaveLength(0)
  expect(screen.queryAllByRole('textbox')).toHaveLength(0)
  expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
  const minutes = screen.queryByRole('link', { name: label('download') })
  if (closed) expect(minutes).toHaveAttribute('href', `/api${URL}/minutes.html`)
  else expect(minutes).toBeNull()
})

it('says when it has no agenda', async () => {
  renderMeeting(makeMeeting({ items: [], attendees: [], guests: '' }), 'viewer')

  expect(await screen.findByText(label('emptyAgenda'))).toBeInTheDocument()
})

it('says when it cannot be loaded', async () => {
  mockApiError('get', URL, 404, 'not_found')
  renderCabinet(
    <Routes>
      <Route path="/d/cabinet/meetings/:id" element={<MeetingPage />} />
    </Routes>,
    { route: '/d/cabinet/meetings/me-1' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})
