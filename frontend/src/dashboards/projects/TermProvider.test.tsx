import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { OLD_TERM, TERM } from './testData'
import { renderProjects } from './testRender'
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
