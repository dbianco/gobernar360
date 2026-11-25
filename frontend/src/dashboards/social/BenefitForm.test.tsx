import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { BenefitForm } from './BenefitForm'
import { BASE, renderSocial } from './testRender'

const label = (key: string) => t(`social.parameters.${key}`)

it('starts without a category when there are none, and says so to the server', async () => {
  const posts = mockApi('post', `${BASE}/benefits`, {}, 201)
  const onDone = vi.fn()
  renderSocial(<BenefitForm categories={[]} onDone={onDone} />)
  const user = userEvent.setup()

  await user.type(await screen.findByRole('textbox', { name: label('name') }), 'Chapas')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onDone).toHaveBeenCalled())
  expect(posts[0].body).toEqual({ category_id: '', name: 'Chapas', description: '' })
})
