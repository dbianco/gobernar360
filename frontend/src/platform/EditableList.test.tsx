import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../test/render'
import { EditableList } from './EditableList'

const ITEMS = [
  { id: 'a', name: 'Centro' },
  { id: 'b', name: 'Norte' },
]

function renderList(overrides: Partial<Parameters<typeof EditableList>[0]> = {}) {
  const props = {
    items: ITEMS,
    addLabel: 'Nueva zona',
    onAdd: vi.fn().mockResolvedValue(true),
    onRename: vi.fn().mockResolvedValue(true),
    onDelete: vi.fn().mockResolvedValue(true),
    ...overrides,
  }
  renderApp(<EditableList {...props} />, { me: null })
  return props
}

it('adds a trimmed name and clears the field once saved', async () => {
  const props = renderList()
  const user = userEvent.setup()
  const field = screen.getByRole('textbox', { name: 'Nueva zona' })

  await user.click(screen.getByRole('button', { name: t('app.add') }))
  expect(props.onAdd).not.toHaveBeenCalled()
  await user.type(field, '  Sur  {Enter}')

  expect(props.onAdd).toHaveBeenCalledWith('Sur')
  await waitFor(() => expect(field).toHaveValue(''))
})

it('keeps the typed name when adding fails', async () => {
  renderList({ onAdd: vi.fn().mockResolvedValue(undefined) })
  const user = userEvent.setup()
  const field = screen.getByRole('textbox', { name: 'Nueva zona' })

  await user.type(field, 'Sur{Enter}')

  expect(field).toHaveValue('Sur')
})

it('renames an item in place', async () => {
  const props = renderList()
  const user = userEvent.setup()

  await user.click(
    screen.getByRole('button', { name: t('app.list.renameNamed', { name: 'Norte' }) }),
  )
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name: 'Norte' }) })
  expect(field).toHaveValue('Norte')
  await user.clear(field)
  await user.click(screen.getByRole('button', { name: t('app.save') }))
  expect(props.onRename).not.toHaveBeenCalled()
  await user.type(field, ' Barrio Norte ')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  expect(props.onRename).toHaveBeenCalledWith(ITEMS[1], 'Barrio Norte')
  await waitFor(() => expect(screen.queryByRole('button', { name: t('app.save') })).toBeNull())
})

it('stays in the rename form when renaming fails, and cancels it', async () => {
  renderList({ onRename: vi.fn().mockResolvedValue(undefined) })
  const user = userEvent.setup()

  await user.click(
    screen.getByRole('button', { name: t('app.list.renameNamed', { name: 'Centro' }) }),
  )
  await user.click(screen.getByRole('button', { name: t('app.save') }))
  expect(screen.getByRole('button', { name: t('app.save') })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('app.cancel') }))

  expect(screen.queryByRole('button', { name: t('app.save') })).toBeNull()
  expect(screen.getByText('Centro')).toBeInTheDocument()
})

it('deletes an item', async () => {
  const props = renderList()
  const user = userEvent.setup()

  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: 'Centro' }) }),
  )

  expect(props.onDelete).toHaveBeenCalledWith(ITEMS[0])
})

it('says when the list is empty unless told not to, and can hide adding', () => {
  const first = renderList({ items: [] })
  expect(screen.getByText(t('app.list.empty'))).toBeInTheDocument()
  expect(first.onAdd).not.toHaveBeenCalled()
})

it('hides the empty text and the add form when asked', () => {
  renderList({ items: [], hideEmpty: true, hideAdd: true })

  expect(screen.queryByText(t('app.list.empty'))).toBeNull()
  expect(screen.queryByRole('textbox', { name: 'Nueva zona' })).toBeNull()
})
