import { Alert, Button, Checkbox, Group, NativeSelect, Stack, Text, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../api/client'
import { dashboardLabelKey } from '../dashboards/registry'
import { useLevelOptions } from './levelOptions'
import type { AccessLevel } from './types'
import { useAction } from './useAction'

/**
 * Adds a member, with per-dashboard access, to the municipality that `base` names.
 *
 * Nobody types a password for someone else: the server emails the person a link to
 * choose one, or a notice if their email already has an account.
 */
export function UserForm(props: {
  /** API prefix of the municipality: "/admin" or "/platform/municipalities/{id}". */
  base: string
  /** Query-key prefix to refresh after saving. */
  scope?: string
  dashboards: string[]
  onDone: (email: string) => void
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const action = useAction([props.scope ?? 'admin'])
  const levelOptions = useLevelOptions()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [grants, setGrants] = useState<Record<string, AccessLevel>>({})

  async function submit(event: FormEvent) {
    event.preventDefault()
    const member = {
      email: email.trim(),
      full_name: fullName.trim(),
      is_admin: isAdmin,
      grants: isAdmin ? {} : grants,
    }
    const saved = await action.run(async () => {
      await api(`${props.base}/users`, { method: 'POST', body: member })
      return true
    })
    if (saved) props.onDone(member.email)
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <TextInput
          label={t('users.name')}
          required
          maxLength={200}
          value={fullName}
          onChange={(event) => setFullName(event.currentTarget.value)}
        />
        <TextInput
          label={t('users.email')}
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.currentTarget.value)}
        />
        <Text size="sm" c="dimmed">
          {t('users.inviteHint')}
        </Text>
        <Checkbox
          label={t('users.admin')}
          checked={isAdmin}
          onChange={(event) => setIsAdmin(event.currentTarget.checked)}
        />
        {!isAdmin &&
          props.dashboards.map((key) => (
            <NativeSelect
              key={key}
              label={t('users.accessTo', {
                dashboard: t(dashboardLabelKey(key) ?? key),
              })}
              value={grants[key] ?? ''}
              data={levelOptions}
              onChange={(event) => {
                const level = event.currentTarget.value as AccessLevel | ''
                setGrants((current) => {
                  const next = { ...current }
                  if (level) next[key] = level
                  else delete next[key]
                  return next
                })
              }}
            />
          ))}
        <Group justify="flex-end">
          {props.onCancel && (
            <Button variant="default" onClick={props.onCancel}>
              {t('app.cancel')}
            </Button>
          )}
          <Button type="submit" loading={action.pending}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
