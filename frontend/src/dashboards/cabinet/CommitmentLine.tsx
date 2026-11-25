import { Anchor, Button, Group, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PostponedBadge } from '../../platform/commitments/PostponedBadge'
import { formatDate } from '../../platform/format'
import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { BASE_PATH } from './api'
import { StateBadge } from './StateBadge'
import type { Commitment } from './types'

/** A commitment inside a meeting or a proposal. */
export function CommitmentLine(props: {
  commitment: Commitment
  /** Next to a title that already says what was agreed. */
  hideName?: boolean
  /** While its meeting is open, one recorded by mistake can be removed. */
  onRemove?: () => void
  onEdit?: () => void
}) {
  const { t } = useTranslation()
  const { commitment } = props
  return (
    <Group justify="space-between" align="flex-start" wrap="nowrap">
      <Stack gap={2} miw={0}>
        <Group gap="xs">
          {!props.hideName && (
            <Anchor component={Link} to={`${BASE_PATH}/commitments/${commitment.id}`}>
              {commitment.description}
            </Anchor>
          )}
          <StateBadge state={commitment.state} />
          <PostponedBadge times={commitment.times_postponed} />
        </Group>
        <Text size="sm" c="dimmed">
          {t('commitments.owed', {
            owner: commitment.owner.full_name,
            date: formatDate(commitment.due_date),
          })}
          {props.hideName && (
            <>
              {' · '}
              <Anchor
                component={Link}
                size="sm"
                to={`${BASE_PATH}/commitments/${commitment.id}`}
                aria-label={t('cabinet.commitment.viewNamed', { name: commitment.description })}
              >
                {t('cabinet.commitment.view')}
              </Anchor>
            </>
          )}
        </Text>
        {commitment.subject && <SubjectLabel subject={commitment.subject} />}
      </Stack>
      {(props.onEdit || props.onRemove) && (
        <Group gap="xs" wrap="nowrap">
          <Button
            size="compact-xs"
            variant="default"
            aria-label={t('cabinet.commitment.editNamed', { name: commitment.description })}
            onClick={props.onEdit}
          >
            {t('app.edit')}
          </Button>
          <Button
            size="compact-xs"
            variant="subtle"
            color="red"
            aria-label={t('cabinet.commitment.removeNamed', { name: commitment.description })}
            onClick={props.onRemove}
          >
            {t('app.delete')}
          </Button>
        </Group>
      )}
    </Group>
  )
}
