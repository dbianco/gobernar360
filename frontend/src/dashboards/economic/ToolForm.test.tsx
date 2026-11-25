import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { BASE, renderEconomic } from './testRender'
import { ToolForm } from './ToolForm'

const label = (key: string) => t(`economic.parameters.${key}`)

it('starts without a category when there are none, and says so to the server', async () => {
  const posts = mockApi('post', `${BASE}/tools`, {}, 201)
  const onDone = vi.fn()
  renderEconomic(<ToolForm categories={[]} subcategories={[]} onDone={onDone} />)
  const user = userEvent.setup()

  await user.type(await screen.findByRole('textbox', { name: label('name') }), 'Taller')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onDone).toHaveBeenCalled())
  expect(posts[0].body).toMatchObject({ name: 'Taller', category_id: '', subcategory_id: null })
})
