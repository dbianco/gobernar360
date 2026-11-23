import { Button, Group, Stack, Text, TextInput } from '@mantine/core'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Pager } from './Pager'
import { PAGE_SIZES, useLocalTable } from './paging'
import { SearchInput } from './SearchInput'

export interface ListItem {
  id: string
  name: string
}

/** A catalog of named items that can be added to, renamed and deleted in place. */
export function EditableList(props: {
  items: ListItem[]
  /** Accessible name of the "new item" field. */
  addLabel: string
  /** Creates an item; without it there is no add form, e.g. when items are created elsewhere. */
  onAdd?: (name: string) => Promise<unknown>
  onRename: (item: ListItem, name: string) => Promise<unknown>
  onDelete: (item: ListItem) => Promise<unknown>
  /** Extra content shown under each item, e.g. its children. */
  renderDetail?: (item: ListItem) => ReactNode
  hideEmpty?: boolean
}) {
  const { t } = useTranslation()
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null)
  // Searched and paged once it no longer fits in the smallest page.
  const table = useLocalTable(`catalog.${props.addLabel}`, props.items, (item) => item.name)
  // A search in progress keeps its box, or it could not be cleared after a deletion.
  const long = props.items.length > PAGE_SIZES[0] || table.query !== ''

  async function rename(event: FormEvent, item: ListItem) {
    event.preventDefault()
    if (!renaming?.name.trim()) return
    if (await props.onRename(item, renaming.name.trim())) setRenaming(null)
  }

  return (
    <Stack gap="xs">
      {props.items.length === 0 && !props.hideEmpty && <Text c="dimmed">{t('app.list.empty')}</Text>}
      {long && (
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={t('app.list.searchHint')}
        />
      )}
      {long && table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
      {table.rows.map((item) => (
        <Stack key={item.id} gap={4}>
          {renaming?.id === item.id ? (
            <form onSubmit={(event) => void rename(event, item)}>
              <Group gap="xs">
                <TextInput
                  aria-label={t('app.list.renameNamed', { name: item.name })}
                  autoFocus
                  maxLength={200}
                  value={renaming.name}
                  onChange={(event) => setRenaming({ id: item.id, name: event.currentTarget.value })}
                />
                <Button type="submit" size="compact-sm">
                  {t('app.save')}
                </Button>
                <Button size="compact-sm" variant="default" onClick={() => setRenaming(null)}>
                  {t('app.cancel')}
                </Button>
              </Group>
            </form>
          ) : (
            <Group gap="xs" justify="space-between" wrap="nowrap">
              <Text>{item.name}</Text>
              <Group gap={4} wrap="nowrap">
                <Button
                  size="compact-xs"
                  variant="default"
                  aria-label={t('app.list.renameNamed', { name: item.name })}
                  onClick={() => setRenaming({ id: item.id, name: item.name })}
                >
                  {t('app.edit')}
                </Button>
                <Button
                  size="compact-xs"
                  variant="subtle"
                  color="red"
                  aria-label={t('app.list.deleteNamed', { name: item.name })}
                  onClick={() => void props.onDelete(item)}
                >
                  {t('app.delete')}
                </Button>
              </Group>
            </Group>
          )}
          {props.renderDetail?.(item)}
        </Stack>
      ))}
      <Pager {...table.pager} />
      {props.onAdd && <AddForm label={props.addLabel} onAdd={props.onAdd} />}
    </Stack>
  )
}

/** The field that creates a new item, cleared once the item exists. */
function AddForm(props: { label: string; onAdd: (name: string) => Promise<unknown> }) {
  const { t } = useTranslation()
  const [newName, setNewName] = useState('')

  async function add(event: FormEvent) {
    event.preventDefault()
    if (!newName.trim()) return
    if (await props.onAdd(newName.trim())) setNewName('')
  }

  return (
    <form onSubmit={(event) => void add(event)}>
      <Group gap="xs">
        <TextInput
          aria-label={props.label}
          placeholder={props.label}
          maxLength={200}
          value={newName}
          onChange={(event) => setNewName(event.currentTarget.value)}
        />
        <Button type="submit" variant="default">
          {t('app.add')}
        </Button>
      </Group>
    </form>
  )
}
