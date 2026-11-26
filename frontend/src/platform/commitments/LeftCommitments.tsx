import { Alert, Button, Group, List, Stack, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../../api/client'
import { useMembers } from '../directory'
import { errorMessage } from '../errorMessage'
import { formatDate } from '../format'
import { PersonSelect } from '../PersonSelect'
import { PATH, send, useCommitmentAction } from './api'
import type { LeftCommitment, LeftCommitments as Left } from './types'

function LeftOne({ commitment }: { commitment: LeftCommitment }) {
  const { t } = useTranslation()
  const members = useMembers()
  const action = useCommitmentAction('admin')
  const [ownerId, setOwnerId] = useState('')

  return (
    <Stack gap={4}>
      <Text size="sm">
        {commitment.description}
        {' · '}
        {t('commitments.owed', {
          owner: commitment.owner.full_name,
          date: formatDate(commitment.due_date),
        })}
      </Text>
      {action.error && <Alert color="red">{action.error}</Alert>}
      {commitment.can_reassign && (
        <Group align="flex-end" gap="xs">
          <PersonSelect
            label={t('commitments.left.newOwner', { name: commitment.description })}
            value={ownerId}
            onChange={setOwnerId}
            people={members.data ?? []}
          />
          <Button
            variant="default"
            loading={action.pending}
            disabled={ownerId === ''}
            aria-label={t('commitments.left.reassignNamed', { name: commitment.description })}
            onClick={() =>
              void action.run(() =>
                send('PATCH', `${PATH}/${commitment.id}`, { owner_id: ownerId }),
              )
            }
          >
            {t('commitments.left.reassign')}
          </Button>
        </Group>
      )}
    </Stack>
  )
}

/**
 * Open commitments of people who are no longer members, for the administrator to give them to
 * somebody. Nothing when there are none.
 */
export function LeftCommitments() {
  const { t } = useTranslation()
  const left = useQuery({
    // Under the administration's key: removing a member refreshes it.
    queryKey: ['admin', 'left-commitments'],
    queryFn: () => api<Left>('/admin/left-commitments'),
  })

  if (left.isError) return <Alert color="red">{errorMessage(left.error)}</Alert>
  if (!left.data || left.data.commitments.length + left.data.hidden === 0) return null
  const { commitments, hidden } = left.data
  return (
    <Alert color="grape" title={t('commitments.left.title')}>
      <Stack gap="sm">
        <Text size="sm">{t('commitments.left.intro')}</Text>
        {commitments.length > 0 && (
          <List listStyleType="none" spacing="sm" aria-label={t('commitments.left.title')}>
            {commitments.map((commitment) => (
              <List.Item key={commitment.id}>
                <LeftOne commitment={commitment} />
              </List.Item>
            ))}
          </List>
        )}
        {hidden > 0 && <Text size="sm">{t('commitments.left.hidden', { count: hidden })}</Text>}
      </Stack>
    </Alert>
  )
}
