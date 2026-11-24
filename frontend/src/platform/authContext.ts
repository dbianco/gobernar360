import { createContext, useContext } from 'react'

import type { Me } from './types'

export interface AuthState {
  /** The signed-in user, or null when signed out. */
  me: Me | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setActiveMunicipality: (municipalityId: string) => Promise<void>
  /** Ask the server again who the user is and where they can work. */
  refresh: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth must be used inside AuthProvider')
  return state
}
