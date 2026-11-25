import { Anchor, Badge, Group, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { formatDate } from '../format'
import { PostponedBadge } from './PostponedBadge'
import type { SubjectCommitment } from './types'

/** Commitments one per line: what was agreed, who owes it, by when and how late it is. */
export function CommitmentLines({ commitments }: { commitments: SubjectCommitment[] }) {
  const { t } = useTranslation()
  return (
    <Stack gap={4} component="ul" m={0} p={0} style={{ listStyle: 'none' }}>
      {commitments.map((commitment) => (
        <Group key={commitment.id} component="li" gap="xs">
          <Anchor component={Link} to={commitment.path} size="sm">
            {commitment.description}
          </Anchor>
          <Text size="sm" c="dimmed">
            {t('commitments.owed', {
              owner: commitment.owner,
              date: formatDate(commitment.due_date),
            })}
          </Text>
          {commitment.overdue && (
            <Badge color="red" variant="light" tt="none">
              {t('commitments.overdue')}
            </Badge>
          )}
          <PostponedBadge times={commitment.times_postponed} />
        </Group>
      ))}
    </Stack>
  )
}
