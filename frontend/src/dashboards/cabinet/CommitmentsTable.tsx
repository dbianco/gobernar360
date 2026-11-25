import { Anchor, Group, Table } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PostponedBadge } from '../../platform/commitments/PostponedBadge'
import { formatDate } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { BASE_PATH } from './api'
import { StateBadge } from './StateBadge'
import type { Commitment } from './types'

export function CommitmentsTable(props: {
  commitments: Commitment[]
  label: string
  /** Left out where every row has the same owner. */
  hideOwner?: boolean
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
            {!props.hideOwner && <HelpTh help={help('owner')}>{label('owner')}</HelpTh>}
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
                <Anchor component={Link} to={`${BASE_PATH}/commitments/${commitment.id}`}>
                  {commitment.description}
                </Anchor>
              </Table.Td>
              {!props.hideOwner && <Table.Td>{commitment.owner.full_name}</Table.Td>}
              <Table.Td>{formatDate(commitment.due_date)}</Table.Td>
              <Table.Td>
                <Group gap={4}>
                  <StateBadge state={commitment.state} />
                  <PostponedBadge times={commitment.times_postponed} />
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
