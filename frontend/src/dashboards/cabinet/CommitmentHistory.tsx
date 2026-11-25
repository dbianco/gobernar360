import { Paper, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { formatDate } from '../../platform/format'
import type { HistoryEntry } from './types'

const DATE_FIELDS = ['due_date', 'completed_on']

function moment(at: string): string {
  return new Intl.DateTimeFormat('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'America/Argentina/Buenos_Aires',
  }).format(new Date(at))
}

/** Progress notes and changes of a commitment, newest first. */
export function CommitmentHistory({ history }: { history: HistoryEntry[] }) {
  const { t } = useTranslation()
  const label = (key: string, options = {}) => t(`cabinet.history.${key}`, options)

  const value = (field: string, raw: string | null) => {
    if (raw === null) return t('app.none')
    if (field === 'state') return t(`cabinet.states.${raw}`)
    return DATE_FIELDS.includes(field) ? formatDate(raw) : raw
  }

  if (history.length === 0) return <Text c="dimmed">{label('empty')}</Text>
  return (
    <Stack gap="xs" role="list">
      {history.map((entry) => (
        <Paper key={entry.id} withBorder p="sm" role="listitem">
          <Text size="xs" c="dimmed">
            {label('by', { author: entry.author ?? label('unknown'), when: moment(entry.at) })}
          </Text>
          {Object.entries(entry.changes).map(([field, [before, after]]) => (
            <Text key={field} size="sm">
              {label('change', {
                field: label(`fields.${field}`),
                before: value(field, before),
                after: value(field, after),
              })}
            </Text>
          ))}
          {entry.note && <Text style={{ whiteSpace: 'pre-wrap' }}>{entry.note}</Text>}
        </Paper>
      ))}
    </Stack>
  )
}
