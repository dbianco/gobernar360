import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe, NOETINGER } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi } from '../test/server'
import { OperatorPage } from './OperatorPage'

const OPERATOR = makeMe({ isOperator: true, municipalities: [] })

function renderOperator() {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: [] }])
  mockApi('get', '/platform/dashboards', ['projects'])
  return renderApp(<OperatorPage />, { me: OPERATOR })
}

it('creates a municipality', async () => {
  const requests = mockApi(
    'post',
    '/platform/municipalities',
    { ...NOETINGER, dashboards: [] },
    201,
  )
  renderOperator()
  const user = userEvent.setup()

  await user.type(await screen.findByRole('textbox', { name: t('platform.name') }), 'Villa María')
  await user.type(screen.getByRole('textbox', { name: t('platform.slug') }), 'villa-maria')
  await user.selectOptions(
    screen.getByRole('combobox', { name: t('platform.kind') }),
    t('platform.kinds.commune'),
  )
  await user.click(screen.getByRole('button', { name: t('platform.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Villa María',
    slug: 'villa-maria',
    kind: 'commune',
  })
})

it('links each municipality to its configuration', async () => {
  renderOperator()

  const link = await screen.findByRole('link', {
    name: t('platform.configureNamed', { name: NOETINGER.name }),
  })
  expect(link).toHaveAttribute('href', `/platform/municipalities/${NOETINGER.id}`)
})

it('lands operators without a municipality on the platform page', async () => {
  mockApi('get', '/platform/municipalities', [])
  mockApi('get', '/platform/dashboards', ['projects'])
  renderApp(<App />, { me: OPERATOR })

  expect(await screen.findByRole('heading', { name: t('platform.title') })).toBeInTheDocument()
  expect(await screen.findByText(t('platform.empty'))).toBeInTheDocument()
})

it('keeps the platform page away from non-operators', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe(), route: '/platform' })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
})
