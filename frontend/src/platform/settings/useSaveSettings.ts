import { useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/client'
import { useSettingsScope } from './scope'
import type { MunicipalitySettings } from './types'

/** Saves the recipients and single sign-on, which the API takes together. */
export function useSaveSettings() {
  const queryClient = useQueryClient()
  const { base, settingsKey } = useSettingsScope()
  return async (body: Pick<MunicipalitySettings, 'notification_emails' | 'sso_enabled'>) => {
    const saved = await api<MunicipalitySettings>(`${base}/settings`, { method: 'PUT', body })
    queryClient.setQueryData(settingsKey, saved)
    return saved
  }
}
