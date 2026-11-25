import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export interface UserRef {
  id: string
  full_name: string
}

/** Everyone in the municipality, by name, for choosing among them. */
export function useMembers() {
  return useQuery({ queryKey: ['directory'], queryFn: () => api<UserRef[]>('/members') })
}

/** The members, plus those already chosen who have left the municipality since. */
export function withFormer(members: UserRef[] | undefined, chosen: UserRef[]): UserRef[] {
  const found = members ?? []
  const former = chosen.filter((person) => !found.some((member) => member.id === person.id))
  return [...former, ...found]
}
