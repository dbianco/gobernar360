import {
  Alert,
  Button,
  Checkbox,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  PasswordInput,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
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

const MIN_PASSWORD_LENGTH = 10

function PasswordForm(props: { url: string; scope: string; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction([props.scope])
  const [password, setPassword] = useState('')
  const [tooShort, setTooShort] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setTooShort(password.length < MIN_PASSWORD_LENGTH)
    if (password.length < MIN_PASSWORD_LENGTH) return
    const saved = await action.run(async () => {
      await api(props.url, { method: 'PUT', body: { password } })
      return true
    })
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <PasswordInput
          label={t('users.newPassword')}
          description={t('users.newPasswordHint')}
          autoComplete="new-password"
          error={tooShort ? t('users.passwordTooShort') : undefined}
          value={password}
          onChange={(event) => setPassword(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={action.pending}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

/**
 * Members of one municipality and what each may do.
 *
 * `base` is the API prefix that names the municipality: "/admin" for the active one,
 * "/platform/municipalities/{id}" for an operator. `scope` is the query-key prefix.
 */
export function MembersPanel(props: {
  base: string
  scope: string[]
  title: string
  /** Operators only: accounts are shared between municipalities. */
  canSetPassword?: boolean
}) {
  const { t } = useTranslation()
  const { base, scope } = props
  const members = useQuery({
    queryKey: [...scope, 'users'],
    queryFn: () => api<Member[]>(`${base}/users`),
  })
  const dashboards = useQuery({
    queryKey: [...scope, 'dashboards'],
    queryFn: () => api<string[]>(`${base}/dashboards`),
  })
  // Changing access also changes what the current user may see.
  const action = useAction([scope[0], 'me'])
  const levelOptions = useLevelOptions()
  const [adding, setAdding] = useState(false)
  const [passwordFor, setPasswordFor] = useState<Member | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const dashboardName = (key: string) => t(dashboardLabelKey(key) ?? key)

  const patch = (member: Member, body: unknown) =>
    action.run(() => api(`${base}/users/${member.membership_id}`, { method: 'PATCH', body }))

  function setLevel(member: Member, key: string, level: string) {
    const grants = { ...member.grants }
    if (level) grants[key] = level as AccessLevel
    else delete grants[key]
    void patch(member, { grants })
  }

  function remove(member: Member) {
    if (!window.confirm(t('users.removeConfirm', { name: member.user.full_name }))) return
    void action.run(() => api(`${base}/users/${member.membership_id}`, { method: 'DELETE' }))
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={props.canSetPassword ? 3 : 2}>{props.title}</Title>
        <Button onClick={() => setAdding(true)}>{t('users.add')}</Button>
      </Group>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {notice && (
        <Alert color="green" withCloseButton onClose={() => setNotice(null)}>
          {notice}
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
                      aria-label={t('users.adminNamed', {
                        name: member.user.full_name,
                      })}
                      checked={member.is_admin}
                      onChange={(event) =>
                        void patch(member, {
                          is_admin: event.currentTarget.checked,
                        })
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
                    <Group gap="xs" justify="flex-end" wrap="nowrap">
                      {props.canSetPassword && (
                        <Button
                          size="compact-xs"
                          variant="default"
                          aria-label={t('users.setPasswordNamed', {
                            name: member.user.full_name,
                          })}
                          onClick={() => setPasswordFor(member)}
                        >
                          {t('users.setPassword')}
                        </Button>
                      )}
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="red"
                        aria-label={t('users.removeNamed', {
                          name: member.user.full_name,
                        })}
                        onClick={() => remove(member)}
                      >
                        {t('users.remove')}
                      </Button>
                    </Group>
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
            base={base}
            scope={scope[0]}
            mayAddExisting={props.canSetPassword}
            dashboards={dashboards.data ?? []}
            onDone={() => setAdding(false)}
            onCancel={() => setAdding(false)}
          />
        )}
      </Modal>
      <Modal
        opened={passwordFor !== null}
        onClose={() => setPasswordFor(null)}
        title={passwordFor ? t('users.setPasswordNamed', { name: passwordFor.user.full_name }) : ''}
      >
        {passwordFor && (
          <PasswordForm
            url={`${base}/users/${passwordFor.membership_id}/password`}
            scope={scope[0]}
            onDone={() => {
              setNotice(
                t('users.passwordChanged', {
                  name: passwordFor.user.full_name,
                }),
              )
              setPasswordFor(null)
            }}
          />
        )}
      </Modal>
    </Stack>
  )
}
