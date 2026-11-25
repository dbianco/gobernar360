import { Alert, Anchor, Group, Loader, NativeSelect, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import { Pager } from '../../platform/Pager'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'
import { BASE, useCommitments, useMembers } from './api'
import { CommitmentsTable } from './CommitmentsTable'
import { STATES } from './types'

/** Every commitment, or those of whoever is signed in. */
export function CommitmentsPage({ mine = false }: { mine?: boolean }) {
  const { t } = useTranslation()
  const [filters, setFilters] = useState({ q: '', state: 'pending', owner_id: '' })
  const paging = usePaging(mine ? 'cabinet.mine' : 'cabinet.commitments')
  const query = { ...filters, mine: mine || undefined }
  const commitments = useCommitments({ ...query, limit: paging.limit, offset: paging.offset })
  fitPage(paging, commitments)
  const members = useMembers()
  const label = (key: string, options = {}) => t(`cabinet.list.${key}`, options)
  const filter = (field: keyof typeof filters) => (value: string) => {
    setFilters((current) => ({ ...current, [field]: value }))
    // A different search starts again from its first page.
    paging.restart()
  }
  const rows = commitments.data?.items ?? []
  const title = t(`cabinet.tabs.${mine ? 'mine' : 'commitments'}`)

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
            ...STATES.map((value) => ({ value, label: t(`cabinet.states.${value}`) })),
            { value: '', label: label('allStates') },
          ]}
        />
        {!mine && (
          <NativeSelect
            label={label('owner')}
            value={filters.owner_id}
            onChange={(event) => filter('owner_id')(event.currentTarget.value)}
            data={[
              { value: '', label: label('allOwners') },
              ...(members.data ?? []).map((member) => ({
                value: member.id,
                label: member.full_name,
              })),
            ]}
          />
        )}
        <Anchor href={downloadUrl(`${BASE}/export/commitments.csv`, query)}>
          {label('download')}
        </Anchor>
      </Group>
      {commitments.isLoading && <Loader aria-label={t('app.loading')} />}
      {commitments.isError && <Alert color="red">{errorMessage(commitments.error)}</Alert>}
      {commitments.data?.total === 0 && (
        <Text c="dimmed">{label(mine ? 'emptyMine' : 'empty')}</Text>
      )}
      {rows.length > 0 && <CommitmentsTable commitments={rows} label={title} hideOwner={mine} />}
      {commitments.data && <Pager {...paging.pager(commitments.data.total)} />}
    </Stack>
  )
}
