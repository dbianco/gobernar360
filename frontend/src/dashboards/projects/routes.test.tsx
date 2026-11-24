import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../../App'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
import { makeSummary, OLD_TERM, TERM } from './testData'
import { BASE, mockCatalogs } from './testRender'

it('clears the filters when the term changes', async () => {
  mockCatalogs()
  const summaries = mockApi('get', `${BASE}/summary`, makeSummary())
  renderApp(<App />, { me: makeMe({ dashboards: { projects: 'viewer' } }), route: '/d/projects' })
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(t('projects.filters.year')), '2024')
  await waitFor(() => expect(summaries.at(-1)?.url.searchParams.get('year')).toBe('2024'))
  await user.selectOptions(
    screen.getByRole('combobox', { name: t('projects.term.change') }),
    OLD_TERM.name,
  )

  await waitFor(() => {
    const last = summaries.at(-1)!.url.searchParams
    expect(last.get('term_id')).toBe(OLD_TERM.id)
    expect(last.get('year')).toBeNull()
  })
  expect(await screen.findByLabelText(t('projects.filters.year'))).toHaveValue('')
  expect(TERM.id).not.toBe(OLD_TERM.id)
})

it('moves between sections with the tabs', async () => {
  mockCatalogs()
  mockApi('get', `${BASE}/summary`, makeSummary())
  mockApi('get', `${BASE}/terms/:termId/budgets`, [])
  renderApp(<App />, { me: makeMe({ dashboards: { projects: 'admin' } }), route: '/d/projects' })
  const user = userEvent.setup()

  await user.click(await screen.findByRole('tab', { name: t('projects.tabs.parameters') }))
  expect(
    await screen.findByRole('tab', { name: t('projects.parameters.terms') }),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: t('projects.tabs.summary') }))

  expect(await screen.findByLabelText(t('projects.filters.year'))).toBeInTheDocument()
})
