import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApiError } from '../../test/server'
import { OLD_TERM, TERM } from './testData'
import { BASE, renderProjects } from './testRender'
import { useTerm } from './termContext'
import { TermSelect } from './TermProvider'

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

it('works without storage, remembering nothing', async () => {
  const read = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('denied')
  })
  const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('denied')
  })
  renderProjects(
    <>
      <TermSelect />
      <CurrentTerm />
    </>,
  )
  const user = userEvent.setup()

  expect(await screen.findByText(`current: ${TERM.name}`)).toBeInTheDocument()
  await user.selectOptions(screen.getByRole('combobox', { name: t('projects.term.change') }), OLD_TERM.name)

  expect(await screen.findByText(`current: ${OLD_TERM.name}`)).toBeInTheDocument()
  expect(write).toHaveBeenCalled()
  read.mockRestore()
  write.mockRestore()
})

it('names the only term instead of offering a choice', async () => {
  renderProjects(<TermSelect />, { terms: [TERM] })

  expect(await screen.findByText(TERM.name)).toBeInTheDocument()
  expect(screen.queryByRole('combobox')).toBeNull()
})

it('says why the terms cannot be loaded', async () => {
  renderProjects(<CurrentTerm />)
  mockApiError('get', `${BASE}/terms`, 500, 'boom')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('refuses to be used outside its provider', () => {
  const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})

  expect(() => render(<CurrentTerm />)).toThrow('useTerm must be used inside TermProvider')
  quiet.mockRestore()
})
