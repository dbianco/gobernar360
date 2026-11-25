import { Alert, Anchor, Group, Loader, NativeSelect, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { STATES } from '../../platform/commitments/types'
import { useMembers } from '../../platform/directory'
import { errorMessage } from '../../platform/errorMessage'
import { Pager } from '../../platform/Pager'
import { fitPage, usePaging } from '../../platform/paging'
import { PersonSelect } from '../../platform/PersonSelect'
import { SearchInput } from '../../platform/SearchInput'
import { BASE, useCommitments } from './api'
import { CommitmentsTable } from './CommitmentsTable'

/** Every commitment taken in a meeting. */
export function CommitmentsPage() {
  const { t } = useTranslation()
  const [filters, setFilters] = useState({ q: '', state: 'pending', owner_id: '' })
  const paging = usePaging('cabinet.commitments')
  const commitments = useCommitments({ ...filters, limit: paging.limit, offset: paging.offset })
  fitPage(paging, commitments)
  const members = useMembers()
  const label = (key: string, options = {}) => t(`cabinet.list.${key}`, options)
  const filter = (field: keyof typeof filters) => (value: string) => {
    setFilters((current) => ({ ...current, [field]: value }))
    // A different search starts again from its first page.
    paging.restart()
  }
  const rows = commitments.data?.items ?? []
  const title = t('cabinet.tabs.commitments')

  return (
    <Stack>
      <Group align="flex-end">
        <SearchInput value={filters.q} onChange={filter('q')} placeholder={label('searchHint')} />
        <NativeSelect
          label={label('state')}
          value={filters.state}
          onChange={(event) => filter('state')(event.currentTarget.value)}
          data={[
            { value: 'pending', label: label('pending') },
            ...STATES.map((value) => ({ value, label: t(`commitments.states.${value}`) })),
            { value: '', label: label('allStates') },
          ]}
        />
        <PersonSelect
          label={label('owner')}
          placeholder={label('allOwners')}
          value={filters.owner_id}
          onChange={filter('owner_id')}
          people={members.data ?? []}
        />
        <Anchor href={downloadUrl(`${BASE}/export/commitments.csv`, filters)}>
          {label('download')}
        </Anchor>
      </Group>
      {commitments.isLoading && <Loader aria-label={t('app.loading')} />}
      {commitments.isError && <Alert color="red">{errorMessage(commitments.error)}</Alert>}
      {commitments.data?.total === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {rows.length > 0 && <CommitmentsTable commitments={rows} label={title} />}
      {commitments.data && <Pager {...paging.pager(commitments.data.total)} />}
    </Stack>
  )
}
