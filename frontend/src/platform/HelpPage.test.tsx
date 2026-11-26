import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { HelpPage } from './HelpPage'

const topic = (key: string) => t(`guide.sections.${key}.title`)
const shown = () =>
  screen
    .getAllByRole('button')
    .map((button) => button.textContent ?? '')
    .filter((text) => text.length > 0)

it('explains the basics to any member, and only that', async () => {
  renderApp(<HelpPage />, { me: makeMe() })

  expect(await screen.findByRole('heading', { name: t('guide.title') })).toBeVisible()
  await screen.findByRole('button', { name: topic('maps') })
  const text = shown().join('|')
  expect(text).toContain(topic('start'))
  expect(text).toContain(topic('maps'))
  expect(text).not.toContain(topic('settings'))
  expect(text).not.toContain(topic('reports'))
  expect(text).not.toContain(topic('operator'))
  // The first topic is open; the rest are one click away.
  expect(screen.getByText(t('guide.sections.start.body.0'))).toBeVisible()
})

it('adds what only the administrators of a municipality do', async () => {
  renderApp(<HelpPage />, { me: makeMe({ isAdmin: true }) })

  await screen.findByRole('button', { name: new RegExp(topic('settings')) })
  const text = shown().join('|')
  expect(text).toContain(topic('settings'))
  expect(text).toContain(topic('reports'))
  expect(text).toContain(topic('notices'))
  expect(text).toContain(t('guide.adminOnly'))
  expect(text).not.toContain(topic('operator'))
})

it('adds the platform for the operator', async () => {
  renderApp(<HelpPage />, { me: makeMe({ isOperator: true }) })

  await screen.findByRole('button', { name: new RegExp(topic('operator')) })
  const text = shown().join('|')
  expect(text).toContain(topic('operator'))
  expect(text).toContain(t('guide.operatorOnly'))
  expect(text).not.toContain(topic('settings'))
})

it('opens a topic when it is clicked', async () => {
  renderApp(<HelpPage />, { me: makeMe() })
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: topic('commitments') }))

  await waitFor(() =>
    expect(screen.getByText(t('guide.sections.commitments.body.0'))).toBeVisible(),
  )
})
