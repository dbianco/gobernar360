import type { State } from './types'

/** The words for a move: leaving the wait for the resident reads as resuming the work. */
export function moveLabelKey(from: State, to: State): string {
  return from === 'waiting' && to === 'in_progress' ? 'resume' : to
}
