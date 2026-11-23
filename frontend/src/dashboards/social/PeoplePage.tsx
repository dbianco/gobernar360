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
  TextInput,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDni } from '../../platform/format'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, usePeople } from './api'
import { PersonForm } from './PersonForm'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** Searchable list of the people incorporated into the dashboard. */
export function PeoplePage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [filters, setFilters] = useState({ q: '', neighborhood: '' })
  const paging = usePaging('social.people')
  const { limit, offset, setOffset } = paging
  const [creating, setCreating] = useState(false)
  const people = usePeople({ ...filters, limit, offset })
  fitPage(paging, people)
  const label = (key: string) => t(`social.people.${key}`)
  const filter = (field: keyof typeof filters) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setFilters((current) => ({ ...current, [field]: value }))
    setOffset(0)
  }

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end">
          <SearchInput
            value={filters.q}
            onChange={(value) => filter('q')({ currentTarget: { value } })}
            placeholder={label('searchHint')}
          />
          <TextInput
            label={label('neighborhoodFilter')}
            maxLength={100}
            value={filters.neighborhood}
            onChange={filter('neighborhood')}
          />
        </Group>
        {hasLevel(me, 'social', 'editor') && (
          <Button onClick={() => setCreating(true)}>{label('create')}</Button>
        )}
      </Group>
      {people.isLoading && <Loader aria-label={t('app.loading')} />}
      {people.isError && <Alert color="red">{errorMessage(people.error)}</Alert>}
      {people.data?.total === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {people.data && people.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={t('social.help.peoplePage.fullName')}>{t('people.fullName')}</HelpTh>
                <HelpTh help={t('social.help.peoplePage.dni')}>{t('people.dni')}</HelpTh>
                <HelpTh help={t('social.help.peoplePage.neighborhood')}>
                  {t('people.neighborhood')}
                </HelpTh>
                <HelpTh help={t('social.help.peoplePage.household')}>{label('household')}</HelpTh>
                <HelpTh help={t('social.help.peoplePage.relationship')}>
                  {label('relationship')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {people.data.items.map((item) => (
                <Table.Tr key={item.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`${BASE_PATH}/people/${item.id}`}>
                      {item.person.full_name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{formatDni(item.person.dni)}</Table.Td>
                  <Table.Td>{item.person.neighborhood || t('app.none')}</Table.Td>
                  <Table.Td>
                    {item.household ? (
                      <Anchor component={Link} to={`${BASE_PATH}/households/${item.household.id}`}>
                        {item.household.name}
                      </Anchor>
                    ) : (
                      <Text span c="dimmed">
                        {label('noHousehold')}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {item.relationship
                      ? t(`social.relationships.${item.relationship}`)
                      : t('app.none')}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {people.data && (
        <Pager {...paging.pager(people.data.total)} />
      )}
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title={label('createTitle')}
        size="lg"
      >
        {creating && <PersonForm onDone={() => setCreating(false)} />}
      </Modal>
    </Stack>
  )
}
