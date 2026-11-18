import { createContext, useContext } from 'react'

import type { Term } from './types'

export interface TermState {
  /** The government term ("gestión") whose plan is being viewed. */
  term: Term
  terms: Term[]
  setTermId: (termId: string) => void
}

export const TermContext = createContext<TermState | null>(null)

export function useTerm(): TermState {
  const state = useContext(TermContext)
  if (!state) throw new Error('useTerm must be used inside TermProvider')
  return state
}

export function latestTerm(terms: Term[]): Term | undefined {
  return [...terms].sort((a, b) => b.start_year - a.start_year)[0]
}

export function termYears(term: Term): number[] {
  return Array.from({ length: term.end_year - term.start_year + 1 }, (_, i) => term.start_year + i)
}
