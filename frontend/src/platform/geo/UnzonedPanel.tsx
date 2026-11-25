import {
  Alert,
  Anchor,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { errorMessage } from '../errorMessage'
import { HelpTh } from '../HelpTh'
import { Pager } from '../Pager'
import { fitPage, usePaging } from '../paging'
import { SearchInput } from '../SearchInput'
import { type UnzonedReason, useUnzoned } from './api'
import type { LocatedKind } from './types'

const REASONS: UnzonedReason[] = ['outside', 'unlocated']

/** Review list: records located outside every zone, or not located yet. */
export function UnzonedPanel({ kind, title }: { kind: LocatedKind; title: string }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState<UnzonedReason>('outside')
  const [q, setQ] = useState('')
  const paging = usePaging(`geo.unzoned.${kind.dashboard}.${kind.record}`)
  const { limit, offset, restart } = paging
  const records = useUnzoned(kind, { reason, q, limit, offset })
  fitPage(paging, records)
  const label = (key: string) => t(`geo.unzoned.${key}`)
  const data = records.data

  return (
    <Paper withBorder p="md" component="section" aria-label={title}>
      <Stack gap="sm">
        <Title order={4}>{title}</Title>
        <Group align="flex-end">
          <SegmentedControl
            aria-label={label('reason')}
            value={reason}
            onChange={(value) => {
              setReason(value as UnzonedReason)
              restart()
            }}
            data={REASONS.map((value) => ({ value, label: label(`reasons.${value}`) }))}
          />
          <SearchInput
            value={q}
            onChange={(value) => {
              setQ(value)
              restart()
            }}
            placeholder={label('searchHint')}
          />
        </Group>
        {records.isLoading && <Loader size="sm" aria-label={t('app.loading')} />}
        {records.isError && <Alert color="red">{errorMessage(records.error)}</Alert>}
        {data?.total === 0 && (
          <Text c="dimmed">{q ? t('app.noMatches') : label(`empty.${reason}`)}</Text>
        )}
        {data && data.items.length > 0 && (
          <Table highlightOnHover aria-label={title}>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={label('recordHelp')}>{label('record')}</HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((record) => (
                <Table.Tr key={record.id}>
                  <Table.Td>
                    <Anchor component={Link} to={kind.path(record.id)}>
                      {record.title}
                    </Anchor>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
        {data && <Pager {...paging.pager(data.total)} />}
      </Stack>
    </Paper>
  )
}
