import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { IndicatorsPage } from './IndicatorsPage'
import { AXES, makeIndicator, TERM } from './testData'
import { BASE, renderProjects } from './testRender'
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

const indicatorLabel = (key: string, options = {}) => t(`projects.indicators.${key}`, options)

it('adds an indicator to an objective with its numbers', async () => {
  mockApi('get', `${BASE}/indicators`, [])
  const created = mockApi('post', `${BASE}/indicators`, makeIndicator(), 201)
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  expect(await screen.findByText(indicatorLabel('empty'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: indicatorLabel('add') }))
  const form = within(await screen.findByRole('dialog'))
  const objective = form.getByRole('combobox', { name: new RegExp(indicatorLabel('objective')) })
  expect(
    within(objective).getByRole('option', { name: 'Ciudad segura › Más iluminación' }),
  ).toBeInTheDocument()
  await user.selectOptions(objective, 'o-2')
  await user.type(
    form.getByRole('textbox', { name: new RegExp(indicatorLabel('name')) }),
    'Luminarias LED',
  )
  await user.type(form.getByRole('textbox', { name: indicatorLabel('unit') }), 'luminarias')
  await user.type(form.getByRole('spinbutton', { name: indicatorLabel('baseline') }), '10')
  await user.type(form.getByRole('spinbutton', { name: indicatorLabel('target') }), '500')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toEqual({
    objective_id: 'o-2',
    name: 'Luminarias LED',
    unit: 'luminarias',
    baseline: '10',
    target: '500',
    current_value: null,
  })
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('edits an indicator, clearing a value it no longer has', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  const changed = mockApi('patch', `${BASE}/indicators/i-1`, makeIndicator())
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: indicatorLabel('editNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByRole('combobox', { name: new RegExp(indicatorLabel('objective')) })).toHaveValue(
    'o-1',
  )
  await user.clear(form.getByRole('spinbutton', { name: indicatorLabel('currentValue') }))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(changed).toHaveLength(1))
  expect(changed[0].body).toMatchObject({ baseline: '120', target: '200', current_value: null })
})

it('cancels the form without saving', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: indicatorLabel('add') }))
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('deletes an indicator and shows why when it cannot', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  const deleted = mockApiError('delete', `${BASE}/indicators/i-1`, 409, 'in_use')
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: indicatorLabel('deleteNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  expect(deleted).toHaveLength(1)
})

it('shows a value without unit or target, and a dash without a current value', async () => {
  mockApi('get', `${BASE}/indicators`, [
    makeIndicator({ unit: '', target: null }),
    makeIndicator({ id: 'i-2', name: 'Sin medición', current_value: null }),
  ])
  renderProjects(<IndicatorsPage />, { level: 'viewer' })

  const plain = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))
  expect(plain.getByText('150')).toBeInTheDocument()
  const unmeasured = within(screen.getByRole('row', { name: /Sin medición/ }))
  expect(unmeasured.getByText('—')).toBeInTheDocument()
})

it('explains that objectives come first, and reports a failed load', async () => {
  mockApiError('get', `${BASE}/indicators`, 500, 'generic')
  renderApp(
    <TermProvider>
      <IndicatorsPage />
    </TermProvider>,
    { me: makeMe({ dashboards: { projects: 'editor' } }), route: '/d/projects' },
  )
  mockApi('get', `${BASE}/terms`, [TERM])
  mockApi('get', `${BASE}/axes`, AXES)
  mockApi('get', `${BASE}/objectives`, [])

  expect(await screen.findByText(indicatorLabel('needsObjectives'))).toBeInTheDocument()
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: indicatorLabel('add') })).toBeNull()
})
