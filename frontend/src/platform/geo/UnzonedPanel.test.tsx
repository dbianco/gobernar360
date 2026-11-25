import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SHOPS, SHOPS_API } from './testData'
import { UnzonedPanel } from './UnzonedPanel'

const PATH = `${SHOPS_API}/unzoned`
const label = (key: string) => t(`geo.unzoned.${key}`)
const records = (...titles: string[]) => titles.map((title, index) => ({ id: `r-${index}`, title }))

function renderPanel() {
  renderApp(<UnzonedPanel kind={SHOPS} title="Para revisar" />, { me: makeMe() })
  return userEvent.setup()
}

it('lists what is outside every zone, each with its screen', async () => {
  const requests = mockApi('get', PATH, { items: records('Campo', 'Vivero'), total: 2 })
  renderPanel()

  expect(await screen.findByRole('link', { name: 'Vivero' })).toHaveAttribute(
    'href',
    '/d/economic/actors/r-1',
  )
  expect(Object.fromEntries(requests[0].url.searchParams)).toEqual({
    reason: 'outside',
    limit: '10',
    offset: '0',
  })
})

it('lists what has no location yet, and searches from the first page', async () => {
  const requests = mockApi('get', PATH, { items: records('Feria'), total: 25 })
  const user = renderPanel()
  await screen.findByRole('link', { name: 'Feria' })
  const last = () => Object.fromEntries(requests[requests.length - 1].url.searchParams)

  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))
  await waitFor(() => expect(last()).toMatchObject({ offset: '10' }))
  await user.click(screen.getByRole('radio', { name: label('reasons.unlocated') }))
  await waitFor(() => expect(last()).toMatchObject({ reason: 'unlocated', offset: '0' }))
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))
  await waitFor(() => expect(last()).toMatchObject({ offset: '10' }))
  await user.type(screen.getByRole('searchbox'), 'x')

  await waitFor(() => expect(last()).toMatchObject({ q: 'x', reason: 'unlocated', offset: '0' }))
})

it('says when there is nothing to review, and when nothing matches', async () => {
  mockApi('get', PATH, { items: [], total: 0 })
  const user = renderPanel()

  expect(await screen.findByText(label('empty.outside'))).toBeInTheDocument()
  await user.click(screen.getByRole('radio', { name: label('reasons.unlocated') }))
  expect(await screen.findByText(label('empty.unlocated'))).toBeInTheDocument()
  await user.type(screen.getByRole('searchbox'), 'x')
  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
})

it('says why the list cannot be shown', async () => {
  mockApiError('get', PATH, 403, 'forbidden')
  renderPanel()

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})
