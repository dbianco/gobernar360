import { createContext, type ReactNode, useContext } from 'react'

export interface ConfirmOptions {
  message: ReactNode
  title?: string
  /** Text of the button that goes ahead; "Confirmar" by default. */
  confirmLabel?: string
  /** For actions that delete or cannot be undone: the button is red. */
  danger?: boolean
}

export type Confirm = (options: ConfirmOptions) => Promise<boolean>

export const ConfirmContext = createContext<Confirm | null>(null)

/**
 * Ask the person to confirm in a modal window, instead of the browser's `confirm()`.
 * Resolves to true when they accept, false when they cancel or close it.
 */
export function useConfirm(): Confirm {
  const confirm = useContext(ConfirmContext)
  if (!confirm) throw new Error('useConfirm needs a <ConfirmProvider> above it.')
  return confirm
}
