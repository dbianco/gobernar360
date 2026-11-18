import {
  Alert,
  Button,
  Checkbox,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../api/client'
import { dashboardLabelKey } from '../dashboards/registry'
import { errorMessage } from './errorMessage'
import { useLevelOptions } from './levelOptions'
import type { AccessLevel } from './types'
import { useAction } from './useAction'
import { UserForm } from './UserForm'

interface Member {
  membership_id: string
  user: { id: string; email: string; full_name: string }
  is_admin: boolean
  grants: Record<string, AccessLevel>
}

/** Members of the active municipality and what each may do. Municipality admins only. */
export function UsersAdminPage() {
  const { t } = useTranslation()
  const members = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api<Member[]>('/admin/users'),
  })
  const dashboards = useQuery({
    queryKey: ['admin', 'dashboards'],
    queryFn: () => api<string[]>('/admin/dashboards'),
  })
  // Changing access also changes what the current user may see.
  const action = useAction(['admin', 'me'])
  const levelOptions = useLevelOptions()
  const [adding, setAdding] = useState(false)
  const dashboardName = (key: string) => t(dashboardLabelKey(key) ?? key)

  const patch = (member: Member, body: unknown) =>
    action.run(() => api(`/admin/users/${member.membership_id}`, { method: 'PATCH', body }))

  function setLevel(member: Member, key: string, level: string) {
    const grants = { ...member.grants }
    if (level) grants[key] = level as AccessLevel
    else delete grants[key]
    void patch(member, { grants })
  }

  function remove(member: Member) {
    if (!window.confirm(t('users.removeConfirm', { name: member.user.full_name }))) return
    void action.run(() => api(`/admin/users/${member.membership_id}`, { method: 'DELETE' }))
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('users.title')}</Title>
        <Button onClick={() => setAdding(true)}>{t('users.add')}</Button>
      </Group>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {members.isLoading && <Loader aria-label={t('app.loading')} />}
      {members.isError && <Alert color="red">{errorMessage(members.error)}</Alert>}
      {members.data && (
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('users.name')}</Table.Th>
                <Table.Th>{t('users.admin')}</Table.Th>
                {dashboards.data?.map((key) => (
                  <Table.Th key={key}>{dashboardName(key)}</Table.Th>
                ))}
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {members.data.map((member) => (
                <Table.Tr key={member.membership_id}>
                  <Table.Td>
                    <Text>{member.user.full_name}</Text>
                    <Text size="sm" c="dimmed">
                      {member.user.email}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Checkbox
                      aria-label={t('users.adminNamed', { name: member.user.full_name })}
                      checked={member.is_admin}
                      onChange={(event) =>
                        void patch(member, { is_admin: event.currentTarget.checked })
                      }
                    />
                  </Table.Td>
                  {dashboards.data?.map((key) => (
                    <Table.Td key={key}>
                      <NativeSelect
                        aria-label={t('users.accessNamed', {
                          dashboard: dashboardName(key),
                          name: member.user.full_name,
                        })}
                        // Administrators always have full access to every enabled dashboard.
                        disabled={member.is_admin}
                        value={member.is_admin ? 'admin' : (member.grants[key] ?? '')}
                        data={levelOptions}
                        onChange={(event) => setLevel(member, key, event.currentTarget.value)}
                      />
                    </Table.Td>
                  ))}
                  <Table.Td>
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      color="red"
                      aria-label={t('users.removeNamed', { name: member.user.full_name })}
                      onClick={() => remove(member)}
                    >
                      {t('users.remove')}
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Modal opened={adding} onClose={() => setAdding(false)} title={t('users.add')}>
        {adding && (
          <UserForm
            dashboards={dashboards.data ?? []}
            onDone={() => setAdding(false)}
            onCancel={() => setAdding(false)}
          />
        )}
      </Modal>
    </Stack>
  )
}
