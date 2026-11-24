import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { IndicatorsPage } from './IndicatorsPage'
import { makeIndicator } from './testData'
import { BASE, mockCatalogs, renderProjects } from './testRender'
import { TermProvider } from './TermProvider'

it('shows the current value against the target', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('150 / 200 cuadras')).toBeInTheDocument()
  expect(row.getByText('75 %')).toBeInTheDocument()
})

it('shows a dash when the indicator has no target', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator({ target: null })])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('—')).toBeInTheDocument()
})

it('hides editing from viewers', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />, { level: 'viewer' })

  await screen.findByRole('row', { name: /Cuadras pavimentadas/ })

  expect(screen.queryByRole('button', { name: t('projects.indicators.add') })).toBeNull()
})

const label = (key: string) => t(`projects.indicators.${key}`)
const field = (key: string) =>
  within(screen.getByRole('dialog')).getByLabelText(label(key), { exact: false })

it('adds an indicator to an objective of the term', async () => {
  mockApi('get', `${BASE}/indicators`, [])
  const posts = mockApi('post', `${BASE}/indicators`, makeIndicator(), 201)
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  await user.click(await screen.findByRole('button', { name: label('add') }))
  const objective = field('objective')
  // Each objective is offered under its axis.
  expect(
    await within(objective).findByRole('option', {
      name: 'Ciudad inclusiva › Reducir el déficit habitacional',
    }),
  ).toBeInTheDocument()
  await user.selectOptions(objective, 'o-2')
  await user.type(field('name'), 'Luminarias')
  await user.type(field('unit'), 'luminarias')
  await user.type(field('baseline'), '300')
  await user.type(field('target'), '1400')
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(posts).toHaveLength(1))
  expect(posts[0].body).toEqual({
    objective_id: 'o-2',
    name: 'Luminarias',
    unit: 'luminarias',
    baseline: '300',
    target: '1400',
    current_value: null,
  })
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('edits an indicator starting from its values', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  const patches = mockApi('patch', `${BASE}/indicators/i-1`, makeIndicator())
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('projects.indicators.editNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )
  expect(field('name')).toHaveValue('Cuadras pavimentadas')
  expect(field('baseline')).toHaveValue(120)
  await user.clear(field('currentValue'))
  await user.type(field('currentValue'), '160')
  await user.clear(field('target'))
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(patches).toHaveLength(1))
  expect(patches[0].body).toMatchObject({ current_value: '160', target: null, objective_id: 'o-1' })
})

it('keeps the form open with the error when saving fails', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  mockApiError('patch', `${BASE}/indicators/i-1`, 422, 'validation_error')
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('projects.indicators.editNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: t('app.save') }))

  expect(
    await within(screen.getByRole('dialog')).findByText(t('errors.validation_error')),
  ).toBeInTheDocument()
  await user.click(
    within(screen.getByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('deletes an indicator, and says why when it cannot', async () => {
  mockApi('get', `${BASE}/indicators`, [
    makeIndicator(),
    makeIndicator({ id: 'i-2', name: 'Otro' }),
  ])
  const deletes = mockApi('delete', `${BASE}/indicators/i-1`, null, 204)
  mockApiError('delete', `${BASE}/indicators/i-2`, 409, 'in_use')
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('projects.indicators.deleteNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )
  await waitFor(() => expect(deletes).toHaveLength(1))
  await user.click(
    screen.getByRole('button', { name: t('projects.indicators.deleteNamed', { name: 'Otro' }) }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('shows values without a unit and an empty current value', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator({ unit: '', current_value: null })])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('— / 200')).toBeInTheDocument()
})

it('asks for objectives before indicators can be added', async () => {
  mockCatalogs()
  mockApi('get', `${BASE}/objectives`, [])
  mockApi('get', `${BASE}/indicators`, [])
  renderApp(
    <TermProvider>
      <IndicatorsPage />
    </TermProvider>,
    { me: makeMe({ dashboards: { projects: 'editor' } }) },
  )

  expect(await screen.findByText(label('needsObjectives'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('add') })).toBeNull()
})

it('shows the error when the indicators cannot be read', async () => {
  mockApiError('get', `${BASE}/indicators`, 500, 'generic')
  renderProjects(<IndicatorsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
