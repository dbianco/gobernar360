import { Badge, Group, List, Paper, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { formatDateTime } from './format'
import type { ResidentNotice } from './types'

const COLORS: Record<ResidentNotice['state'], string> = {
  queued: 'blue',
  handed_over: 'teal',
  failed: 'red',
  no_channel: 'orange',
}

/** Handing over reads differently by each channel; the other states read the same. */
const stateKey = ({ state, channel }: ResidentNotice) =>
  state === 'handed_over' ? `handed_over_${channel}` : state

/** Whether the resident was told how their complaint ended, and by what. For editors. */
export function NoticesPanel({ notices }: { notices: ResidentNotice[] }) {
  const { t } = useTranslation()
  const label = (key: string) => t(`complaints.notices.${key}`)
  const throughCidi = notices.some(
    ({ channel, state }) => channel === 'cidi' && state === 'handed_over',
  )

  return (
    <Paper withBorder p="md" component="section" aria-label={label('title')}>
      <Title order={4} mb="xs">
        {label('title')}
      </Title>
      {notices.length === 0 ? (
        <Text c="dimmed">{label('none')}</Text>
      ) : (
        <List listStyleType="none" spacing="xs">
          {notices.map((notice) => (
            <List.Item key={notice.id}>
              <Group gap="sm">
                <Badge variant="light" color={COLORS[notice.state]} tt="none">
                  {label(`states.${stateKey(notice)}`)}
                </Badge>
                <Text size="sm">{label(`kinds.${notice.kind}`)}</Text>
                <Text size="sm" c="dimmed">
                  {formatDateTime(notice.handed_over_at ?? notice.created_at)}
                </Text>
              </Group>
            </List.Item>
          ))}
        </List>
      )}
      {notices.some(({ state }) => state === 'no_channel') && (
        <Text size="xs" c="dimmed" mt="xs">
          {label('noChannelHelp')}
        </Text>
      )}
      {throughCidi && (
        <Text size="xs" c="dimmed" mt="xs">
          {label('cidiHelp')}
        </Text>
      )}
    </Paper>
  )
}
