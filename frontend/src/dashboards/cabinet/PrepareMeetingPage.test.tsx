import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { PrepareMeetingPage } from './PrepareMeetingPage'
import {

  LEO,
  makeAgendaProposal,
  makeMeeting,
  makeProposal,
  makeRow,
  page,
  PROPOSALS,
} from './testData'
import { BASE, renderCabinet } from './testRender'
import type { AgendaProposal } from './types'

const label = (key: string, options = {}) => t(`cabinet.prepare.${key}`, options)
const CLOSED = makeRow({ closed: true })

function renderPrepare(proposal: AgendaProposal = makeAgendaProposal(), meetings = [CLOSED]) {
  mockApi('get', `${BASE}/meetings`, page(meetings))
  const proposals = mockApi('get', `${BASE}/agenda-proposal`, proposal)
  renderCabinet(
    <Routes>
      <Route path="/d/cabinet/meetings/new" element={<PrepareMeetingPage />} />
      <Route path="/d/cabinet/meetings/:id" element={<p>the meeting</p>} />
    </Routes>,
    { route: '/d/cabinet/meetings/new' },
  )
  return { proposals, user: userEvent.setup() }
}

const rows = () => screen.findAllByRole('listitem')
const titles = async () =>
  (await rows()).map(
    (row) => within(row).getByRole<HTMLInputElement>('checkbox').labels?.[0].textContent,
  )
const submit = () => screen.findByRole('button', { name: label('submit') })

it('proposes the agenda for today, saying where each item comes from', async () => {
  const { proposals } = renderPrepare()

  const [light, commitment, carried] = (await rows()).map((row) => within(row))
  expect(proposals[0].url.searchParams.get('date')).toBe('2026-11-23')
  expect(light.getByRole('checkbox', { name: 'Ambiental, octubre de 2026' })).toBeChecked()
  expect(light.getByText(t('cabinet.agenda.sources.light'))).toBeInTheDocument()
  expect(light.getByRole('link', { name: t('status.states.red') })).toBeInTheDocument()
  expect(commitment.getByText(t('cabinet.agenda.sources.commitment'))).toBeInTheDocument()
  expect(commitment.getByText(t('cabinet.states.overdue'))).toBeInTheDocument()
  expect(commitment.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  expect(carried.getByText(t('cabinet.agenda.carried'))).toBeInTheDocument()
  expect(screen.getByText(label('carryOver', { count: 2 }))).toBeInTheDocument()
  expect(screen.getByLabelText(t('cabinet.meeting.date'))).toHaveAttribute('min', '2026-10-20')
  expect(screen.queryByText(/no tenés acceso/)).toBeNull()
})

it('creates the meeting with what was accepted, in the order chosen', async () => {
  const { user } = renderPrepare()
  const posts = mockApi('post', `${BASE}/meetings`, makeMeeting(), 201)
  await rows()

  await user.click(screen.getByRole('checkbox', { name: 'Certificar la obra' }))
  await user.type(screen.getByLabelText(label('newItem')), ' Feria del libro {Enter}')
  await user.click(
    screen.getByRole('button', { name: t('cabinet.agenda.moveUp', { name: 'Feria del libro' }) }),
  )
  await user.click(
    screen.getByRole('button', {
      name: t('cabinet.agenda.moveDown', { name: 'Ambiental, octubre de 2026' }),
    }),
  )
  expect(await titles()).toEqual([
    'Certificar la obra',
    'Ambiental, octubre de 2026',
    'Feria del libro',
    'Cronograma',
  ])
  await user.click(screen.getByRole('combobox', { name: t('cabinet.meeting.attendees') }))
  await user.click(await screen.findByRole('option', { name: LEO.full_name }))
  await user.type(screen.getByLabelText(t('cabinet.meeting.guests')), 'Prensa')
  await user.click(await submit())

  expect(await screen.findByText('the meeting')).toBeInTheDocument()
  expect(posts[0].body).toEqual({
    date: '2026-11-23',
    attendee_ids: [LEO.id],
    guests: 'Prensa',
    agenda: [
      { key: 'light:environment:2026-10' },
      { title: 'Feria del libro' },
      { key: 'item:it-7' },
    ],
  })
})

it('takes back what was dropped', async () => {
  const { user } = renderPrepare()
  await rows()
  const box = () => screen.getByRole('checkbox', { name: 'Cronograma' })

  await user.click(box())
  expect(box()).not.toBeChecked()
  await user.click(box())
  expect(box()).toBeChecked()
})

it('adds items with the button and not without a title', async () => {
  const { user } = renderPrepare(makeAgendaProposal({ proposals: [], to_carry_over: 0 }))

  expect(await screen.findByText(label('nothing'))).toBeInTheDocument()
  const add = screen.getByRole('button', { name: t('app.add') })
  expect(add).toBeDisabled()
  await user.type(screen.getByLabelText(label('newItem')), '  {Enter}')
  expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  await user.type(screen.getByLabelText(label('newItem')), 'Feria')
  await user.click(add)

  expect(await titles()).toEqual(['Feria'])
  expect(screen.getByLabelText(label('newItem'))).toHaveValue('')
  expect(screen.queryByText(/se arrastra/)).toBeNull()
})

it('proposes again for another date and keeps the decisions taken', async () => {
  const { user, proposals } = renderPrepare()
  await rows()
  await user.click(screen.getByRole('checkbox', { name: 'Cronograma' }))
  mockApi(
    'get',
    `${BASE}/agenda-proposal`,
    makeAgendaProposal({
      proposals: [...PROPOSALS, makeProposal({ key: 'light:social:2026-10', title: 'Social' })],
    }),
  )

  fireEvent.change(screen.getByLabelText(t('cabinet.meeting.date')), {
    target: { value: '2026-12-01' },
  })

  expect(await screen.findByRole('checkbox', { name: 'Social' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Cronograma' })).not.toBeChecked()
  expect(proposals).toHaveLength(1)
})

it('asks for a date before proposing or creating anything', async () => {
  const { proposals } = renderPrepare()
  await rows()

  fireEvent.change(screen.getByLabelText(t('cabinet.meeting.date')), { target: { value: '' } })

  await waitFor(async () => expect(await submit()).toBeDisabled())
  expect(proposals).toHaveLength(1)
})

it('says how many dashboards it did not look at', async () => {
  renderPrepare(makeAgendaProposal({ dashboards_not_considered: 3 }))

  expect(await screen.findByText(label('notConsidered', { count: 3 }))).toBeInTheDocument()
})

it('loads the proposal again when it changed meanwhile', async () => {
  const { user, proposals } = renderPrepare()
  mockApiError('post', `${BASE}/meetings`, 409, 'agenda_changed')
  await rows()

  await user.click(await submit())

  expect(await screen.findByText(t('errors.agenda_changed'))).toBeInTheDocument()
  await waitFor(() => expect(proposals).toHaveLength(2))
})

it('leads to the open meeting instead, when there is one', async () => {
  renderPrepare(makeAgendaProposal(), [makeRow()])

  expect(await screen.findByText(label('alreadyOpen'))).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: t('cabinet.meetings.continue', { date: '23/11/2026' }) }),
  ).toHaveAttribute('href', '/d/cabinet/meetings/me-1')
})

it('says when the proposal or the members cannot be loaded', async () => {
  renderPrepare()
  mockApiError('get', `${BASE}/agenda-proposal`, 500, 'boom')
  mockApiError('get', `${BASE}/members`, 500, 'boom')

  await waitFor(() => expect(screen.getAllByText(t('errors.generic'))).toHaveLength(2))
  expect(await submit()).toBeDisabled()
})
