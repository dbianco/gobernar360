import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../test/render'
import { EditableList, type ListItem } from './EditableList'

const ITEMS: ListItem[] = [
  { id: 'd-1', name: 'Obras Públicas' },
  { id: 'd-2', name: 'Salud' },
]

function renderList(
  overrides: Partial<Parameters<typeof EditableList>[0]> = {},
  items: ListItem[] = ITEMS,
) {
  const handlers = {
    onAdd: vi.fn().mockResolvedValue(true),
    onRename: vi.fn().mockResolvedValue(true),
    onDelete: vi.fn().mockResolvedValue(true),
  }
  renderApp(
    <EditableList items={items} addLabel="Nueva dependencia" {...handlers} {...overrides} />,
    { me: null },
  )
  return { ...handlers, ...overrides }
}

const renameButton = (name: string) =>
  screen.getByRole('button', { name: t('app.list.renameNamed', { name }) })
const renameField = (name: string) =>
  screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })

it('adds an item, trimmed, and clears the field once added', async () => {
  const { onAdd } = renderList()
  const user = userEvent.setup()
  const field = screen.getByRole('textbox', { name: 'Nueva dependencia' })

  await user.type(field, '  Hacienda  {Enter}')

  expect(onAdd).toHaveBeenCalledWith('Hacienda')
  expect(field).toHaveValue('')
})

it('keeps what was typed when adding fails', async () => {
  const onAdd = vi.fn().mockResolvedValue(undefined)
  renderList({ onAdd })
  const field = screen.getByRole('textbox', { name: 'Nueva dependencia' })

  await userEvent.type(field, 'Hacienda{Enter}')

  expect(field).toHaveValue('Hacienda')
})

it('does not add an empty name', async () => {
  const { onAdd } = renderList()

  await userEvent.type(screen.getByRole('textbox', { name: 'Nueva dependencia' }), '   {Enter}')

  expect(onAdd).not.toHaveBeenCalled()
})

it('renames an item in place', async () => {
  const { onRename } = renderList()
  const user = userEvent.setup()

  await user.click(renameButton('Salud'))
  const field = renameField('Salud')
  expect(field).toHaveValue('Salud')
  await user.clear(field)
  await user.type(field, ' Salud y Ambiente {Enter}')

  expect(onRename).toHaveBeenCalledWith(ITEMS[1], 'Salud y Ambiente')
  expect(screen.queryByRole('textbox', { name: t('app.list.renameNamed', { name: 'Salud' }) }))
    .toBeNull()
})

it('stays in place when renaming fails or the name is empty, and can be cancelled', async () => {
  const onRename = vi.fn().mockResolvedValue(undefined)
  renderList({ onRename })
  const user = userEvent.setup()

  await user.click(renameButton('Salud'))
  await user.clear(renameField('Salud'))
  await user.click(screen.getByRole('button', { name: t('app.save') }))
  expect(onRename).not.toHaveBeenCalled()
  await user.type(renameField('Salud'), 'Otra{Enter}')
  expect(onRename).toHaveBeenCalledOnce()
  expect(renameField('Salud')).toHaveValue('Otra')

  await user.click(screen.getByRole('button', { name: t('app.cancel') }))

  expect(screen.getByText('Salud')).toBeInTheDocument()
})

it('deletes an item', async () => {
  const { onDelete } = renderList()

  await userEvent.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: 'Obras Públicas' }) }),
  )

  expect(onDelete).toHaveBeenCalledWith(ITEMS[0])
})

it('says when it is empty, unless told not to, and can hide the add form', () => {
  renderList({}, [])
  expect(screen.getByText(t('app.list.empty'))).toBeInTheDocument()
})

it('can leave out the empty message and the add form', () => {
  renderList({ hideEmpty: true, hideAdd: true, renderDetail: (item) => <i>{item.id}</i> }, [])

  expect(screen.queryByText(t('app.list.empty'))).toBeNull()
  expect(screen.queryByRole('textbox')).toBeNull()
})

it('shows the detail of each item under it', () => {
  renderList({ renderDetail: (item) => <i>detalle {item.id}</i> })

  expect(screen.getByText('detalle d-2')).toBeInTheDocument()
})
