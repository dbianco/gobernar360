import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useMemo } from 'react'

import {
  api,
  ApiError,
  setMunicipalitySuspendedHandler,
  setSessionLostHandler,
} from '../api/client'
import { AuthContext, type AuthState } from './authContext'
import type { Me } from './types'

const ME_KEY = ['me']

async function fetchMe(): Promise<Me | null> {
  try {
    return await api<Me>('/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ME_KEY,
    queryFn: fetchMe,
    staleTime: 60_000,
    // Access changed by an administrator shows up when the user returns to the tab.
    refetchOnWindowFocus: true,
  })

  /** Replace the user and drop every cached answer, which belonged to the previous identity. */
  const replaceMe = useCallback(
    async (me: Me | null) => {
      // A profile refresh still in flight would otherwise land afterwards and restore
      // the previous identity, e.g. showing a signed-out user as signed in.
      await queryClient.cancelQueries({ queryKey: ME_KEY })
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'me' })
      queryClient.setQueryData(ME_KEY, me)
    },
    [queryClient],
  )

  const refresh = useCallback(async () => {
    try {
      await replaceMe(await fetchMe())
    } catch {
      // Unreachable server: keep what is on screen; the next request will tell.
    }
  }, [replaceMe])

  // An expired or revoked session sends the user back to the login page.
  useEffect(() => {
    setSessionLostHandler(() => void replaceMe(null))
    return () => setSessionLostHandler(null)
  }, [replaceMe])

  // A suspended municipality drops out of the profile; its data on screen goes with it.
  useEffect(() => {
    setMunicipalitySuspendedHandler(() => void refresh())
    return () => setMunicipalitySuspendedHandler(null)
  }, [refresh])

  const state = useMemo<AuthState>(
    () => ({
      me: data ?? null,
      isLoading,
      login: async (email, password) => {
        await replaceMe(
          await api<Me>('/auth/login', { method: 'POST', body: { email, password } }),
        )
      },
      logout: async () => {
        try {
          await api('/auth/logout', { method: 'POST' })
        } catch {
          // The session may already be gone or the server unreachable; sign out here regardless.
        }
        await replaceMe(null)
      },
      refresh,
      setActiveMunicipality: async (municipalityId) => {
        await replaceMe(
          await api<Me>('/auth/active-municipality', {
            method: 'POST',
            body: { municipality_id: municipalityId },
          }),
        )
      },
    }),
    [data, isLoading, replaceMe, refresh],
  )

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}
