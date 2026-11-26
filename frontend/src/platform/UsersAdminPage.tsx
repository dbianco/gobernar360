import { Stack } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { LeftCommitments } from './commitments/LeftCommitments'
import { MembersPanel } from './MembersPanel'

/** Members of the active municipality and what each may do. Municipality admins only. */
export function UsersAdminPage() {
  const { t } = useTranslation()
  return (
    <Stack>
      <LeftCommitments />
      <MembersPanel base="/admin" scope={['admin']} title={t('users.title')} />
    </Stack>
  )
}
