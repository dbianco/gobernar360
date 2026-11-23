import { screen } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

import { t } from './render'

/** Rename the catalog item `name` to `newName`, then delete it, as a person would. */
export async function renameThenDelete(user: UserEvent, name: string, newName: string) {
  await user.click(await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }))
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, `${newName}{Enter}`)
  await user.click(await screen.findByRole('button', { name: t('app.list.deleteNamed', { name }) }))
}
