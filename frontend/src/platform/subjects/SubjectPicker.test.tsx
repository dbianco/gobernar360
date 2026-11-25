import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SubjectPicker } from './SubjectPicker'
import type { Subject } from './types'

const PLAZA: Subject = {
  access: 'visible',
  kind: 'project',
  dashboard_key: 'projects',
  ref: 'pr-1',
  label: 'Plaza central',
  path: '/d/projects/projects/pr-1',
  color: null,
}
const BACHEO: Subject = { ...PLAZA, ref: 'pr-2', label: 'Bacheo' }
const OCTOBER: Subject = {
  ...PLAZA,
  kind: 'month',
  ref: '2026-10',
  label: 'Proyectos, octubre de 2026',
  color: 'red',
}
const KINDS = [
  { dashboard_key: 'projects', kind: 'month' },
  { dashboard_key: 'projects', kind: 'project' },
  { dashboard_key: 'demo', kind: 'thing' },
]
const kindLabel = () => screen.findByRole('combobox', { name: t('subjects.about') })
const which = () => screen.findByRole('combobox', { name: t('subjects.which') })

function renderPicker(initial?: Subject | null) {
  const onChange = vi.fn()
  mockApi('get', '/subjects/kinds', KINDS)
  const searches = mockApi('get', '/subjects/search', ({ url }) => {
    if (url.searchParams.get('kind') === 'month') return [OCTOBER]
    const q = url.searchParams.get('q') ?? ''
    return [PLAZA, BACHEO].filter((project) => project.label!.toLowerCase().includes(q))
  })
  renderApp(<SubjectPicker initial={initial} onChange={onChange} />, { me: makeMe() })
  return { onChange, searches, user: userEvent.setup() }
}

const optionNames = async () =>
  (await screen.findAllByRole('option', { hidden: false }))
    .filter((option) => option.tagName !== 'OPTION')
    .map((option) => option.textContent)

it('offers every kind the API lists, also those of dashboards it does not know', async () => {
  const { searches } = renderPicker()

  const select = within(await kindLabel())
  await select.findByRole('option', { name: /demo/ })
  expect(select.getAllByRole('option').map((option) => option.textContent)).toEqual([
    t('subjects.none'),
    `${t('projects.title')}: ${t('subjects.kinds.month')}`,
    `${t('projects.title')}: ${t('subjects.kinds.projects.project')}`,
    `demo: ${t('subjects.kinds.record')}`,
  ])
  // Nothing to search until a kind is chosen.
  expect(searches).toHaveLength(0)
  expect(screen.queryByRole('combobox', { name: t('subjects.which') })).toBeNull()
})

it('searches the records on the server and gives the one chosen', async () => {
  const { user, onChange, searches } = renderPicker()
  await screen.findByRole('option', { name: /demo/ })

  await user.selectOptions(await kindLabel(), 'projects/project')
  await user.click(await which())
  await waitFor(async () => expect(await optionNames()).toEqual(['Plaza central', 'Bacheo']))
  await user.type(await which(), 'bac')
  await waitFor(async () => expect(await optionNames()).toEqual(['Bacheo']))
  await user.click(screen.getByRole('option', { name: 'Bacheo' }))

  expect(onChange).toHaveBeenLastCalledWith({
    dashboard_key: 'projects',
    kind: 'project',
    ref: 'pr-2',
  })
  const last = searches.find(({ url }) => url.searchParams.get('q') === 'bac')
  expect(Object.fromEntries(last!.url.searchParams)).toEqual({
    dashboard_key: 'projects',
    kind: 'project',
    q: 'bac',
    limit: '24',
  })
  expect(await which()).toHaveValue('Bacheo')
})

it('offers months with their state', async () => {
  const { user, onChange } = renderPicker()
  await screen.findByRole('option', { name: /demo/ })

  await user.selectOptions(await kindLabel(), 'projects/month')
  await user.click(await which())
  await user.click(
    await screen.findByRole('option', {
      name: `Proyectos, octubre de 2026 (${t('status.states.red')})`,
    }),
  )

  expect(onChange).toHaveBeenLastCalledWith({
    dashboard_key: 'projects',
    kind: 'month',
    ref: '2026-10',
  })
})

it('starts from what was linked and lets it go', async () => {
  const { user, onChange } = renderPicker(BACHEO)

  await waitFor(async () => expect(await kindLabel()).toHaveValue('projects/project'))
  expect(await which()).toHaveValue('Bacheo')
  expect(onChange).not.toHaveBeenCalled()
  await user.selectOptions(await kindLabel(), '')

  expect(onChange).toHaveBeenLastCalledWith(null)
  expect(screen.queryByRole('combobox', { name: t('subjects.which') })).toBeNull()
})

it('keeps what is linked as an option though a search does not find it', async () => {
  const { user } = renderPicker({ ...PLAZA, ref: 'pr-9', label: 'Obra vieja' })

  await user.click(await which())

  await waitFor(async () =>
    expect(await optionNames()).toEqual(['Obra vieja', 'Plaza central', 'Bacheo']),
  )
})

it('forgets the record when another kind is chosen', async () => {
  const { user, onChange } = renderPicker(PLAZA)
  await screen.findByRole('option', { name: /demo/ })

  await user.selectOptions(await kindLabel(), 'projects/month')

  expect(onChange).toHaveBeenLastCalledWith(null)
  expect(await which()).toHaveValue('')
})

it('starts empty when what was linked cannot be read', async () => {
  renderPicker({
    ...PLAZA,
    access: 'restricted',
    ref: null,
    label: null,
    path: null,
  })

  await screen.findByRole('option', { name: /demo/ })
  expect(await kindLabel()).toHaveValue('')
})

it('says when the kinds or the records cannot be loaded', async () => {
  mockApiError('get', '/subjects/kinds', 500, 'boom')
  renderApp(<SubjectPicker onChange={() => undefined} />, { me: makeMe() })

  expect(await screen.findByRole('alert')).toHaveTextContent(t('errors.generic'))
})
