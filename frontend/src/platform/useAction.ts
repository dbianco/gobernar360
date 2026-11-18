import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'

import { errorMessage } from './errorMessage'

/**
 * Runs a change against the API. On success the queries under `invalidate` are
 * refreshed; on failure `error` holds a message to show.
 */
export function useAction(invalidate: string[]) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const keys = invalidate.join('|')

  const run = useCallback(
    async <T>(action: () => Promise<T>): Promise<T | undefined> => {
      setPending(true)
      setError(null)
      try {
        const result = await action()
        await Promise.all(
          keys.split('|').map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
        )
        return result
      } catch (caught) {
        setError(errorMessage(caught))
        return undefined
      } finally {
        setPending(false)
      }
    },
    [queryClient, keys],
  )

  return { run, error, pending, clearError: () => setError(null) }
}
