import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/access'
import { BASE_PATH, useHouseholds } from './api'
import { HouseholdForm } from './HouseholdForm'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** Searchable list of the households (family groups) of the dashboard. */
export function HouseholdsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [q, setQ] = useState('')
  const paging = usePaging('social.households')
  const { limit, offset, setOffset } = paging
  const [creating, setCreating] = useState(false)
  const households = useHouseholds({ q, limit, offset })
  fitPage(paging, households)
  const label = (key: string) => t(`social.households.${key}`)

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <SearchInput
          value={q}
          onChange={(value) => {
            setQ(value)
            setOffset(0)
          }}
          placeholder={label('searchHint')}
        />
        {hasLevel(me, 'social', 'editor') && (
          <Button onClick={() => setCreating(true)}>{label('create')}</Button>
        )}
      </Group>
      {households.isLoading && <Loader aria-label={t('app.loading')} />}
      {households.isError && <Alert color="red">{errorMessage(households.error)}</Alert>}
      {households.data?.total === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {households.data && households.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={t('social.help.householdsPage.name')}>{label('name')}</HelpTh>
                <HelpTh help={t('social.help.householdsPage.address')}>{label('address')}</HelpTh>
                <HelpTh help={t('social.help.householdsPage.neighborhood')}>
                  {label('neighborhood')}
                </HelpTh>
                <HelpTh help={t('social.help.householdsPage.head')}>{label('head')}</HelpTh>
                <HelpTh help={t('social.help.householdsPage.members')} ta="right">
                  {label('members')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {households.data.items.map((household) => (
                <Table.Tr key={household.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`${BASE_PATH}/households/${household.id}`}>
                      {household.name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{household.address || t('app.none')}</Table.Td>
                  <Table.Td>{household.neighborhood || t('app.none')}</Table.Td>
                  <Table.Td>
                    {household.head?.full_name ?? (
                      <Text span c="dimmed">
                        {label('noHead')}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td ta="right">{household.member_count}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {households.data && (
        <Pager {...paging.pager(households.data.total)} />
      )}
      <Modal opened={creating} onClose={() => setCreating(false)} title={label('createTitle')}>
        {creating && <HouseholdForm onDone={() => setCreating(false)} />}
      </Modal>
    </Stack>
  )
}
