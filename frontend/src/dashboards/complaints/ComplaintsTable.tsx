import { Anchor, Stack, Table, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { formatDate } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { BASE_PATH } from './api'
import { ClockBadge, StateBadge } from './Badges'
import { clockText, formatDay } from './format'
import { type Complaint, OPEN_STATES } from './types'

/** Complaints with their state and clock; used by the list and by the areas' queues. */
export function ComplaintsTable(props: {
  complaints: Complaint[]
  showArea?: boolean
  label: string
}) {
  const { t } = useTranslation()
  const label = (key: string, options = {}) => t(`complaints.table.${key}`, options)
  const help = (key: string) => t(`complaints.help.table.${key}`)

  return (
    <Table.ScrollContainer minWidth={900}>
      <Table highlightOnHover aria-label={props.label}>
        <Table.Thead>
          <Table.Tr>
            <HelpTh help={help('number')}>{label('number')}</HelpTh>
            <HelpTh help={help('received')}>{label('received')}</HelpTh>
            <HelpTh help={help('type')}>{label('type')}</HelpTh>
            {props.showArea && <HelpTh help={help('area')}>{label('area')}</HelpTh>}
            <HelpTh help={help('zone')}>{label('zone')}</HelpTh>
            <HelpTh help={help('address')}>{label('address')}</HelpTh>
            <HelpTh help={help('state')}>{label('state')}</HelpTh>
            <HelpTh help={help('deadline')}>{label('deadline')}</HelpTh>
            <HelpTh help={help('situation')}>{label('situation')}</HelpTh>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {props.complaints.map((complaint) => {
            const open = OPEN_STATES.includes(complaint.state)
            return (
              <Table.Tr key={complaint.id}>
                <Table.Td>
                  <Anchor
                    component={Link}
                    to={`${BASE_PATH}/complaints/${complaint.id}`}
                    aria-label={label('openNamed', { number: complaint.number })}
                  >
                    {complaint.number}
                  </Anchor>
                </Table.Td>
                <Table.Td>{formatDay(complaint.received_at)}</Table.Td>
                <Table.Td>{complaint.type.name}</Table.Td>
                {props.showArea && <Table.Td>{complaint.area.name}</Table.Td>}
                <Table.Td>{complaint.zone.name}</Table.Td>
                <Table.Td>{complaint.address}</Table.Td>
                <Table.Td>
                  <StateBadge state={complaint.state} />
                </Table.Td>
                <Table.Td>{open ? formatDate(complaint.clock.deadline) : t('app.none')}</Table.Td>
                <Table.Td>
                  <Stack gap={2}>
                    <ClockBadge clock={complaint.clock} state={complaint.state} />
                    <Text size="xs" c="dimmed">
                      {clockText(complaint.clock, complaint.state, t)}
                    </Text>
                  </Stack>
                </Table.Td>
              </Table.Tr>
            )
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
