import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { EditableList } from './EditableList'

const items = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: `i-${index + 1}`,
    name: index === 0 ? 'Área de Niñez' : `Área ${index + 1}`,
  }))

function renderList(count: number) {
  return renderApp(
    <EditableList
      items={items(count)}
      addLabel="Nueva área"
      onAdd={vi.fn()}
      onRename={vi.fn()}
      onDelete={vi.fn()}
    />,
    { me: makeMe() },
  )
}

it('shows a short catalog whole, without search or pager', async () => {
  renderList(8)

  expect(await screen.findByText('Área 8')).toBeInTheDocument()
  expect(screen.queryByRole('searchbox')).toBeNull()
  expect(screen.queryByRole('button', { name: t('app.pager.next') })).toBeNull()
})

it('pages a long catalog ten at a time and searches it ignoring accents', async () => {
  renderList(25)
  const user = userEvent.setup()

  expect(await screen.findByText('Área 10')).toBeInTheDocument()
  expect(screen.queryByText('Área 11')).toBeNull()
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))
  expect(await screen.findByText('Área 11')).toBeInTheDocument()

  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'ninez')

  expect(screen.getByText('Área de Niñez')).toBeInTheDocument()
  expect(screen.queryByText('Área 11')).toBeNull()
})

it('remembers the page size chosen for the catalog', async () => {
  const view = renderList(25)
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByRole('combobox', { name: t('app.pager.pageSize') }),
    t('app.pager.perPage', { count: 50 }),
  )
  expect(await screen.findByText('Área 25')).toBeInTheDocument()
  view.unmount()
  renderList(25)

  expect(await screen.findByText('Área 25')).toBeInTheDocument()
})

function renderEditable(
  handlers: {
    onAdd?: (name: string) => Promise<unknown>
    onRename?: (item: { id: string; name: string }, name: string) => Promise<unknown>
    onDelete?: (item: { id: string; name: string }) => Promise<unknown>
  } = {},
  options: { withoutAdd?: boolean; hideEmpty?: boolean; items?: { id: string; name: string }[] } = {},
) {
  const props = {
    onAdd: vi.fn(handlers.onAdd ?? (async () => true)),
    onRename: vi.fn(handlers.onRename ?? (async () => true)),
    onDelete: vi.fn(handlers.onDelete ?? (async () => true)),
  }
  renderApp(
    <EditableList
      items={options.items ?? items(2)}
      addLabel="Nueva área"
      hideEmpty={options.hideEmpty}
      renderDetail={(item) => <small>detalle de {item.name}</small>}
      {...props}
      onAdd={options.withoutAdd ? undefined : props.onAdd}
    />,
    { me: makeMe() },
  )
  return { ...props, user: userEvent.setup() }
}

it('adds an item with its name trimmed, and clears the field once added', async () => {
  const { onAdd, user } = renderEditable()
  const field = await screen.findByRole('textbox', { name: 'Nueva área' })

  await user.type(field, '  Cultura  ')
  await user.click(screen.getByRole('button', { name: t('app.add') }))

  expect(onAdd).toHaveBeenCalledWith('Cultura')
  await waitFor(() => expect(field).toHaveValue(''))
})

it('keeps what was typed when adding fails, and ignores a blank name', async () => {
  const { onAdd, user } = renderEditable({ onAdd: async () => undefined })
  const field = await screen.findByRole('textbox', { name: 'Nueva área' })

  await user.type(field, '   ')
  await user.click(screen.getByRole('button', { name: t('app.add') }))
  expect(onAdd).not.toHaveBeenCalled()

  await user.type(field, 'Cultura')
  await user.click(screen.getByRole('button', { name: t('app.add') }))
  expect(onAdd).toHaveBeenCalledWith('Cultura')
  expect(field).toHaveValue('   Cultura')
})

it('renames an item in place', async () => {
  const { onRename, user } = renderEditable()

  await user.click(
    await screen.findByRole('button', { name: t('app.list.renameNamed', { name: 'Área 2' }) }),
  )
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name: 'Área 2' }) })
  expect(field).toHaveValue('Área 2')
  await user.clear(field)
  await user.type(field, ' Área dos ')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  expect(onRename).toHaveBeenCalledWith({ id: 'i-2', name: 'Área 2' }, 'Área dos')
  await waitFor(() => expect(screen.queryByRole('button', { name: t('app.save') })).toBeNull())
})

it('keeps the rename open when it fails, ignores a blank name and can be cancelled', async () => {
  const { onRename, user } = renderEditable({ onRename: async () => undefined })

  await user.click(
    await screen.findByRole('button', { name: t('app.list.renameNamed', { name: 'Área 2' }) }),
  )
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name: 'Área 2' }) })
  await user.clear(field)
  await user.click(screen.getByRole('button', { name: t('app.save') }))
  expect(onRename).not.toHaveBeenCalled()

  await user.type(field, 'Otra')
  await user.click(screen.getByRole('button', { name: t('app.save') }))
  expect(onRename).toHaveBeenCalledTimes(1)
  expect(field).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: t('app.cancel') }))
  expect(screen.queryByRole('textbox', { name: /Área 2/ })).toBeNull()
  expect(screen.getByText('Área 2')).toBeInTheDocument()
})

it('deletes an item and shows what each item details', async () => {
  const { onDelete, user } = renderEditable()

  expect(await screen.findByText('detalle de Área 2')).toBeInTheDocument()
  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: 'Área 2' }) }),
  )

  expect(onDelete).toHaveBeenCalledWith({ id: 'i-2', name: 'Área 2' })
})

it('says when it is empty unless told not to, and offers no add form without a way to add', async () => {
  renderEditable({}, { items: [], withoutAdd: true })

  expect(await screen.findByText(t('app.list.empty'))).toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: 'Nueva área' })).toBeNull()
})

it('hides the empty message when asked', async () => {
  renderEditable({}, { items: [], hideEmpty: true })

  await screen.findByRole('textbox', { name: 'Nueva área' })
  expect(screen.queryByText(t('app.list.empty'))).toBeNull()
})

it('says when nothing in a long catalog matches the search', async () => {
  renderList(12)
  const user = userEvent.setup()

  await user.type(await screen.findByRole('searchbox', { name: t('app.search') }), 'zzz')

  expect(screen.getByText(t('app.noMatches'))).toBeInTheDocument()
})
