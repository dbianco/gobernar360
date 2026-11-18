import { useTranslation } from 'react-i18next'

/** Access levels offered when granting a dashboard; the empty value means no access. */
export function useLevelOptions() {
  const { t } = useTranslation()
  return [
    { value: '', label: t('users.levels.none') },
    { value: 'viewer', label: t('users.levels.viewer') },
    { value: 'editor', label: t('users.levels.editor') },
    { value: 'admin', label: t('users.levels.admin') },
  ]
}
