import { screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApiError } from '../../test/server'
import { OLD_TERM, TERM } from './testData'
import { BASE, mockCatalogs, renderProjects } from './testRender'
import { TermProvider, TermSelect } from './TermProvider'
import { useTerm } from './termContext'

function CurrentTerm() {
  return <p>current: {useTerm().term.name}</p>
}

it('defaults to the most recent term', async () => {
  renderProjects(<CurrentTerm />, { terms: [OLD_TERM, TERM] })

  expect(await screen.findByText(`current: ${TERM.name}`)).toBeInTheDocument()
})

it('remembers the term chosen earlier', async () => {
  window.localStorage.setItem('g360.projects.term', OLD_TERM.id)

  renderProjects(<CurrentTerm />)

  expect(await screen.findByText(`current: ${OLD_TERM.name}`)).toBeInTheDocument()
})

it('ignores a remembered term that no longer exists', async () => {
  window.localStorage.setItem('g360.projects.term', 'gone')

  renderProjects(<CurrentTerm />)

  expect(await screen.findByText(`current: ${TERM.name}`)).toBeInTheDocument()
})

it('shows an empty state when there are no terms', async () => {
  renderProjects(<CurrentTerm />, { terms: [], level: 'admin' })

  expect(await screen.findByText(t('projects.term.emptyTitle'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('projects.term.goToParameters') })).toBeInTheDocument()
  expect(screen.queryByText(/current:/)).not.toBeInTheDocument()
})

it('does not offer parameters to members who cannot manage them', async () => {
  renderProjects(<CurrentTerm />, { terms: [], level: 'editor' })

  expect(await screen.findByText(t('projects.term.emptyViewerBody'))).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: t('projects.term.goToParameters') })).toBeNull()
})

it('works when the browser refuses to remember the term', async () => {
  const blocked = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('storage is blocked')
  })

  renderProjects(<CurrentTerm />)

  expect(await screen.findByText(`current: ${TERM.name}`)).toBeInTheDocument()
  blocked.mockRestore()
})

it('shows the error when the terms cannot be read', async () => {
  mockCatalogs()
  mockApiError('get', `${BASE}/terms`, 500, 'generic')
  renderApp(
    <TermProvider>
      <CurrentTerm />
    </TermProvider>,
    { me: makeMe({ dashboards: { projects: 'viewer' } }) },
  )

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('shows the only term as text instead of a choice', async () => {
  renderProjects(<TermSelect />, { terms: [TERM] })

  expect(await screen.findByText(TERM.name)).toBeInTheDocument()
  expect(screen.queryByRole('combobox')).toBeNull()
})
