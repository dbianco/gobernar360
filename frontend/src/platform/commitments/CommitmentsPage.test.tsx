import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { choosePerson } from '../../test/person'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { CommitmentsPage } from './CommitmentsPage'
import { ANA, HIDDEN, LEO, makeCommitment, makeInformal, page, ZOE } from './testData'
import { renderCommitments } from './testRender'

const label = (key: string) => t(`commitments.list.${key}`)
const form = (key: string) => t(`commitments.form.${key}`)
const tab = (key: string) => screen.findByRole('tab', { name: t(`commitments.relations.${key}`) })
const last = <T,>(items: T[]) => items[items.length - 1]
const dialog = async () => within(await screen.findByRole('dialog'))

it('lists what one owes: until when, how it is, about what and where it comes from', async () => {
  const requests = mockApi(
    'get',
    '/commitments',
    page([
      makeCommitment(),
      makeInformal(),
      makeCommitment({ id: 'co-3', description: 'De otros', origin: null, subject: HIDDEN }),
      makeCommitment({ id: 'co-4', description: 'De lejos', origin: null, source: 'complaints' }),
    ]),
  )
  renderCommitments(<CommitmentsPage />)

  const meeting = within(await screen.findByRole('row', { name: /Certificar/ }))
  expect(meeting.getByRole('link', { name: 'Certificar la obra' })).toHaveAttribute(
    'href',
    '/commitments/co-1',
  )
  expect(meeting.getByText('20/11/2026')).toBeInTheDocument()
  expect(meeting.getByText(t('commitments.states.overdue'))).toBeInTheDocument()
  expect(meeting.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  expect(meeting.getByRole('link', { name: 'Plaza central' })).toBeInTheDocument()
  expect(meeting.getByRole('link', { name: 'Reunión del 20/10/2026' })).toHaveAttribute(
    'href',
    '/d/cabinet/meetings/me-0',
  )
  // Everything here is theirs.
  expect(meeting.queryByText(LEO.full_name)).toBeNull()
  const informal = within(screen.getByRole('row', { name: /Enviar la nota/ }))
  expect(informal.getByText(t('commitments.informal'))).toBeInTheDocument()
  const hidden = within(screen.getByRole('row', { name: /De otros/ }))
  expect(hidden.getByText(t('cabinet.title'))).toBeInTheDocument()
  expect(hidden.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  // A dashboard this build does not know.
  expect(screen.getByRole('row', { name: /De lejos/ })).toHaveTextContent('complaints')
  expect(Object.fromEntries(last(requests).url.searchParams)).toEqual({
    relation: 'mine',
    state: 'pending',
    limit: '10',
    offset: '0',
  })
})

it('moves between those one owes, gave and follows, each with who owes it', async () => {
  const requests = mockApi('get', '/commitments', page([makeInformal()]))
  renderCommitments(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await tab('given'))
  const table = await screen.findByRole('table', { name: t('commitments.relations.given') })
  expect(within(table).getByText(LEO.full_name)).toBeInTheDocument()
  expect(last(requests).url.searchParams.get('relation')).toBe('given')
  await user.click(await tab('following'))
  await waitFor(() => expect(last(requests).url.searchParams.get('relation')).toBe('following'))
  await user.click(await tab('mine'))
  expect(await tab('mine')).toHaveAttribute('aria-selected', 'true')
})

it('opens on the list asked for, or on one\'s own', async () => {
  mockApi('get', '/commitments', page([]))
  const view = renderCommitments(<CommitmentsPage />, '/commitments?list=given')
  expect(await tab('given')).toHaveAttribute('aria-selected', 'true')
  view.unmount()

  renderCommitments(<CommitmentsPage />, '/commitments?list=nothing')
  expect(await tab('mine')).toHaveAttribute('aria-selected', 'true')
})

it('searches and filters on the server, from the first page', async () => {
  const requests = mockApi('get', '/commitments', page([makeInformal()], 30))
  renderCommitments(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.pager.next') }))
  await user.type(screen.getByRole('searchbox'), 'nota')
  await user.selectOptions(screen.getByLabelText(label('state')), 'done')

  await waitFor(() => expect(last(requests).url.searchParams.get('state')).toBe('done'))
  const params = last(requests).url.searchParams
  expect([params.get('q'), params.get('offset')]).toEqual(['nota', '0'])
  await user.selectOptions(screen.getByLabelText(label('state')), label('allStates'))
  await waitFor(() => expect(last(requests).url.searchParams.has('state')).toBe(false))
})

it.each(['mine', 'given', 'following'])('says when the list of %s is empty', async (relation) => {
  mockApi('get', '/commitments', page([]))
  renderCommitments(<CommitmentsPage />, `/commitments?list=${relation}`)

  expect(await screen.findByText(label(`empty.${relation}`))).toBeInTheDocument()
})

it('says when the list cannot be loaded', async () => {
  mockApiError('get', '/commitments', 500, 'boom')
  renderCommitments(<CommitmentsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('gives somebody a commitment and attaches others to be told when it is done', async () => {
  mockApi('get', '/commitments', page([]))
  const posts = mockApi('post', '/commitments', makeInformal(), 201)
  renderCommitments(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('commitments.create') }))
  const box = await dialog()
  await user.type(box.getByLabelText(form('description')), 'Enviar la nota')
  await choosePerson(
    user,
    box.getByRole('combobox', { name: form('owner') }),
    'paz',
    LEO.full_name,
  )
  fireEvent.change(box.getByLabelText(form('dueDate')), { target: { value: '01/12/2026' } })
  const followers = box.getByRole('combobox', { name: form('followers') })
  await choosePerson(user, followers, 'gomez', ANA.full_name)
  await choosePerson(user, followers, 'zoe', ZOE.full_name)
  await user.selectOptions(box.getByLabelText(t('subjects.about')), 'projects/project')
  await user.click(await box.findByRole('combobox', { name: t('subjects.which') }))
  await user.click(await screen.findByRole('option', { name: 'Plaza central' }))
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(posts[0].body).toEqual({
    description: 'Enviar la nota',
    owner_id: LEO.id,
    due_date: '2026-12-01',
    follower_ids: [ANA.id, ZOE.id],
    subject: { dashboard_key: 'projects', kind: 'project', ref: 'pr-1' },
  })
})

it('gives oneself one, with nobody attached and about nothing', async () => {
  mockApi('get', '/commitments', page([]))
  const posts = mockApi('post', '/commitments', makeInformal(), 201)
  renderCommitments(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('commitments.create') }))
  const box = await dialog()
  await user.type(box.getByLabelText(form('description')), 'Ordenar el archivo')
  await choosePerson(user, box.getByRole('combobox', { name: form('owner') }), ANA.full_name)
  fireEvent.change(box.getByLabelText(form('dueDate')), { target: { value: '01/12/2026' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(posts).toHaveLength(1))
  expect(posts[0].body).toEqual({
    description: 'Ordenar el archivo',
    owner_id: ANA.id,
    due_date: '2026-12-01',
    follower_ids: [],
    subject: null,
  })
})

it('is not sent without saying who', async () => {
  mockApi('get', '/commitments', page([]))
  const posts = mockApi('post', '/commitments', makeInformal(), 201)
  renderCommitments(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('commitments.create') }))
  const box = await dialog()
  await user.type(box.getByLabelText(form('description')), 'x')
  fireEvent.change(box.getByLabelText(form('dueDate')), { target: { value: '01/12/2026' } })
  await user.click(box.getByRole('button', { name: t('app.save') }))

  expect(posts).toHaveLength(0)
  await user.click(box.getByRole('button', { name: t('app.cancel') }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('keeps the form open and says why it failed, and closes it with Escape', async () => {
  mockApi('get', '/commitments', page([]))
  mockApiError('post', '/commitments', 422, 'invalid_reference')
  renderCommitments(<CommitmentsPage />)
  mockApiError('get', '/members', 500, 'boom')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('commitments.create') }))
  const box = await dialog()

  expect(await box.findByText(t('errors.generic'))).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})
