import { Alert, Anchor, Badge, Button, Group, Loader, Stack, Table, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/access'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'
import { BASE_PATH, KEY, useMeetings, useOpenMeeting } from './api'

/** Cabinet meetings, the latest first, and the way into the next one. */
export function MeetingsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [q, setQ] = useState('')
  const paging = usePaging('cabinet.meetings')
  const meetings = useMeetings({ q, limit: paging.limit, offset: paging.offset })
  fitPage(paging, meetings)
  const latest = useOpenMeeting()
  const label = (key: string, options = {}) => t(`cabinet.meetings.${key}`, options)
  const help = (key: string) => t(`cabinet.help.meetingsPage.${key}`)
  const rows = meetings.data?.items ?? []

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <SearchInput
          value={q}
          onChange={(value) => {
            setQ(value)
            paging.restart()
          }}
          placeholder={label('searchHint')}
        />
        {hasLevel(me, KEY, 'editor') &&
          latest.data &&
          (latest.open ? (
            <Button component={Link} to={`${BASE_PATH}/meetings/${latest.open.id}`}>
              {label('continue', { date: formatDate(latest.open.date) })}
            </Button>
          ) : (
            <Button component={Link} to={`${BASE_PATH}/meetings/new`}>
              {label('prepare')}
            </Button>
          ))}
      </Group>
      {meetings.isLoading && <Loader aria-label={t('app.loading')} />}
      {meetings.isError && <Alert color="red">{errorMessage(meetings.error)}</Alert>}
      {meetings.data?.total === 0 && <Text c="dimmed">{q ? t('app.noMatches') : label('empty')}</Text>}
      {rows.length > 0 && (
        <Table.ScrollContainer minWidth={480}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('date')}>{label('date')}</HelpTh>
                <HelpTh help={help('state')}>{label('state')}</HelpTh>
                <HelpTh help={help('items')} ta="right">
                  {label('items')}
                </HelpTh>
                <HelpTh help={help('commitments')} ta="right">
                  {label('commitments')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((meeting) => (
                <Table.Tr key={meeting.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`${BASE_PATH}/meetings/${meeting.id}`}>
                      {formatDate(meeting.date)}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" tt="none" color={meeting.closed ? 'gray' : 'blue'}>
                      {t(meeting.closed ? 'cabinet.meeting.closed' : 'cabinet.meeting.open')}
                    </Badge>
                  </Table.Td>
                  <Table.Td ta="right">{meeting.items}</Table.Td>
                  <Table.Td ta="right">{meeting.commitments}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {meetings.data && <Pager {...paging.pager(meetings.data.total)} />}
    </Stack>
  )
}
