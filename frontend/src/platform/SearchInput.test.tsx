import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../test/render'
import { SearchInput } from './SearchInput'

it('passes on what is typed, and offers to clear it only when there is something', async () => {
  const onChange = vi.fn()
  const { unmount } = renderApp(
    <SearchInput value="" onChange={onChange} placeholder="Nombre o DNI" />,
    { me: null },
  )
  const user = userEvent.setup()

  const box = screen.getByRole('searchbox', { name: t('app.search') })
  expect(box).toHaveAttribute('placeholder', 'Nombre o DNI')
  expect(box).toHaveAttribute('maxlength', '100')
  expect(screen.queryByRole('button', { name: t('app.clearSearch') })).toBeNull()
  await user.type(box, 'a')
  expect(onChange).toHaveBeenLastCalledWith('a')

  unmount()

  renderApp(<SearchInput value="pérez" onChange={onChange} placeholder="Nombre o DNI" />, {
    me: null,
  })
  await user.click(screen.getByRole('button', { name: t('app.clearSearch') }))
  expect(onChange).toHaveBeenLastCalledWith('')
})

it('can be named for what it searches', () => {
  renderApp(<SearchInput value="" onChange={vi.fn()} placeholder="x" label="Buscar hitos" />, {
    me: null,
  })

  expect(screen.getByRole('searchbox', { name: 'Buscar hitos' })).toBeInTheDocument()
})
