import { screen } from '@testing-library/react'
import type userEvent from '@testing-library/user-event'

import { t } from './render'

type User = ReturnType<typeof userEvent.setup>

/** Rename an item of an EditableList in place. */
export async function renameItem(user: User, name: string, next: string) {
  await user.click(
    await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }),
  )
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, `${next}{Enter}`)
}

/** Delete an item of an EditableList, once the list shows it. */
export async function deleteItem(user: User, name: string) {
  await user.click(
    await screen.findByRole('button', { name: t('app.list.deleteNamed', { name }) }),
  )
}
