import { createContext, useContext } from 'react'

/**
 * Whose configuration the settings screens edit: where its API lives and the query keys
 * its data is cached under. A municipality's administrators edit their own; the platform
 * operator edits the municipality named in the address.
 */
export interface SettingsScope {
  /** API path the settings routes hang from, e.g. "/admin". */
  base: string
  /** Prefix of the query keys, so two municipalities never share cached data. */
  key: string[]
}

export const OWN_MUNICIPALITY: SettingsScope = { base: '/admin', key: ['admin'] }

export const SettingsScopeContext = createContext<SettingsScope>(OWN_MUNICIPALITY)

export function useSettingsScope() {
  const scope = useContext(SettingsScopeContext)
  return {
    base: scope.base,
    settingsKey: [...scope.key, 'settings'],
    templatesKey: [...scope.key, 'email-templates'],
  }
}
