import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { TypeForm } from './TypeForm'
import { LAMP, LIGHTS, WORKS } from './testData'
import { BASE } from './testRender'

const label = (key: string) => t(`complaints.parameters.${key}`)

it('starts from the first area and nothing else for a new type', () => {
  renderApp(<TypeForm areas={[WORKS, LIGHTS]} onDone={() => undefined} />, { me: null })

  expect(screen.getByLabelText(label('name'))).toHaveValue('')
  expect(screen.getByLabelText(label('area'))).toHaveValue(WORKS.id)
})

it('offers no area while the municipality has none', () => {
  renderApp(<TypeForm areas={[]} onDone={() => undefined} />, { me: null })

  expect(screen.getByLabelText(label('area'))).toBeEmptyDOMElement()
})

it('saves the changes of a type and closes', async () => {
  const patches = mockApi('patch', `${BASE}/types/${LAMP.id}`, LAMP)
  const done = vi.fn()
  renderApp(<TypeForm areas={[LIGHTS, WORKS]} type={LAMP} onDone={done} />, { me: null })
  const user = userEvent.setup()

  await user.selectOptions(screen.getByLabelText(label('area')), WORKS.id)
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await vi.waitFor(() => expect(done).toHaveBeenCalledOnce())
  expect(patches[0].body).toEqual({
    name: LAMP.name,
    area_id: WORKS.id,
    target_days: 3,
    is_active: true,
  })
})

it('stays open and says why when it is refused', async () => {
  mockApiError('patch', `${BASE}/types/${LAMP.id}`, 403, 'forbidden')
  const done = vi.fn()
  renderApp(<TypeForm areas={[LIGHTS]} type={LAMP} onDone={done} />, { me: null })

  await userEvent.click(screen.getByRole('button', { name: t('app.save') }))

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(done).not.toHaveBeenCalled()
})
