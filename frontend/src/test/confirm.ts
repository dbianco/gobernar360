import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

import { t } from './render'

/**
 * Answer the confirmation modal (`useConfirm`) titled `title`: accept with its main
 * button, or cancel. Returns the modal's text, to check what was asked.
 */
export async function answerConfirm(
  user: UserEvent,
  accept: boolean,
  title: string = t('app.confirmTitle'),
): Promise<string> {
  const dialog = await screen.findByRole('dialog', { name: title })
  const question = dialog.textContent ?? ''
  const buttons = within(dialog).getAllByRole('button')
  const cancel = within(dialog).getByRole('button', { name: t('app.cancel') })
  // The confirming button is the last one; the first may be the modal's close button.
  await user.click(accept ? buttons[buttons.length - 1] : cancel)
  return question
}
