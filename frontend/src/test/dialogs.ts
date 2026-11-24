import { screen, waitFor } from '@testing-library/react'
import type userEvent from '@testing-library/user-event'
import { expect } from 'vitest'

/** Close the open dialog with Escape, and wait until it is gone. */
export async function closeDialog(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

/** Let pending requests land, to check that none was made. */
export const settle = () => new Promise((resolve) => setTimeout(resolve, 50))
