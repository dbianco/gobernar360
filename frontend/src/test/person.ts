import { screen } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

/** Choose somebody in a list of people, typing part of the name as a person would. */
export async function choosePerson(
  user: UserEvent,
  box: HTMLElement,
  typed: string,
  name: string = typed,
) {
  await user.click(box)
  await user.clear(box)
  await user.type(box, typed)
  await user.click(await screen.findByRole('option', { name }))
}
