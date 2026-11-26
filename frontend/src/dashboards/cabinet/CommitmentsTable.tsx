import { Anchor, Group, Table, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PATH } from '../../platform/commitments/api'
import { OwnerLeftBadge } from '../../platform/commitments/OwnerLeftBadge'
import { PostponedBadge } from '../../platform/commitments/PostponedBadge'
import { StateBadge } from '../../platform/commitments/StateBadge'
import { formatDate } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { BASE_PATH } from './api'
import type { Commitment } from './types'

export function CommitmentsTable(props: {
  commitments: Commitment[]
  label: string
}) {
  const { t } = useTranslation()
  const label = (key: string) => t(`cabinet.list.${key}`)
  const help = (key: string) => t(`cabinet.help.list.${key}`)

  return (
    <Table.ScrollContainer minWidth={760}>
      <Table highlightOnHover aria-label={props.label}>
        <Table.Thead>
          <Table.Tr>
            <HelpTh help={help('description')}>{label('description')}</HelpTh>
            <HelpTh help={help('owner')}>{label('owner')}</HelpTh>
            <HelpTh help={help('dueDate')}>{label('dueDate')}</HelpTh>
            <HelpTh help={help('state')}>{label('state')}</HelpTh>
            <HelpTh help={help('subject')}>{label('subject')}</HelpTh>
            <HelpTh help={help('meeting')}>{label('meeting')}</HelpTh>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {props.commitments.map((commitment) => (
            <Table.Tr key={commitment.id}>
              <Table.Td>
                <Anchor component={Link} to={`${PATH}/${commitment.id}`}>
                  {commitment.description}
                </Anchor>
              </Table.Td>
              <Table.Td>{commitment.owner.full_name}</Table.Td>
              <Table.Td>
                {formatDate(commitment.due_date)}
                {commitment.agreed_due_date !== commitment.due_date && (
                  <Text size="xs" c="dimmed">
                    {t('commitments.agreedFor', { date: formatDate(commitment.agreed_due_date) })}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>
                <Group gap={4}>
                  <StateBadge state={commitment.state} />
                  <PostponedBadge times={commitment.times_postponed} />
                  <OwnerLeftBadge commitment={commitment} />
                </Group>
              </Table.Td>
              <Table.Td>
                {commitment.subject ? <SubjectLabel subject={commitment.subject} /> : t('app.none')}
              </Table.Td>
              <Table.Td>
                <Anchor
                  component={Link}
                  size="sm"
                  to={`${BASE_PATH}/meetings/${commitment.meeting.id}`}
                >
                  {formatDate(commitment.meeting.date)}
                </Anchor>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
