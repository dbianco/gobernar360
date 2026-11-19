import { useTranslation } from 'react-i18next'

import { MembersPanel } from './MembersPanel'

/** Members of the active municipality and what each may do. Municipality admins only. */
export function UsersAdminPage() {
  const { t } = useTranslation()
  return <MembersPanel base="/admin" scope={['admin']} title={t('users.title')} />
}
