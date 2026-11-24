import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  NativeSelect,
  Paper,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import { dashboardLabelKey } from '../dashboards/registry'
import { errorMessage } from './errorMessage'
import { KINDS, useMunicipalities } from './operatorApi'
import { Pager } from './Pager'
import { useLocalTable } from './paging'
import { SearchInput } from './SearchInput'
import { useAction } from './useAction'

/** Platform operator: the municipalities of the platform and the form to add one. */
export function OperatorPage() {
  const { t } = useTranslation()
  const municipalities = useMunicipalities()
  const table = useLocalTable(
    'platform.municipalities',
    municipalities.data,
    (municipality) => `${municipality.name} ${municipality.slug}`,
  )
  const action = useAction(['platform', 'me'])
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [kind, setKind] = useState<string>('municipality')

  async function create(event: FormEvent) {
    event.preventDefault()
    const created = await action.run(() =>
      api('/platform/municipalities', {
        method: 'POST',
        body: { name: name.trim(), slug: slug.trim(), kind },
      }),
    )
    if (created) {
      setName('')
      setSlug('')
    }
  }

  return (
    <Stack>
      <Title order={2}>{t('platform.title')}</Title>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {municipalities.isLoading && <Loader aria-label={t('app.loading')} />}
      {municipalities.isError && <Alert color="red">{errorMessage(municipalities.error)}</Alert>}
      {municipalities.data?.length === 0 && <Text c="dimmed">{t('platform.empty')}</Text>}
      {table.hasItems && (
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={t('platform.searchHint')}
        />
      )}
      {table.hasItems && table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
      {table.rows.length > 0 && (
        <Table.ScrollContainer minWidth={560}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('platform.name')}</Table.Th>
                <Table.Th>{t('platform.kind')}</Table.Th>
                <Table.Th>{t('platform.dashboardsFor')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((municipality) => (
                <Table.Tr key={municipality.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <Text>{municipality.name}</Text>
                      {municipality.suspension && (
                        <Badge color="red" variant="light" style={{ textTransform: 'none' }}>
                          {t('platform.suspension.badge')}
                        </Badge>
                      )}
                    </Group>
                    <Text size="sm" c="dimmed">
                      {municipality.slug}
                    </Text>
                  </Table.Td>
                  <Table.Td>{t(`platform.kinds.${municipality.kind}`)}</Table.Td>
                  <Table.Td>
                    {municipality.dashboards.length === 0
                      ? t('platform.noDashboards')
                      : municipality.dashboards
                          .map((key) => t(dashboardLabelKey(key) ?? key))
                          .join(', ')}
                  </Table.Td>
                  <Table.Td ta="right">
                    <Anchor
                      component={Link}
                      to={`/platform/municipalities/${municipality.id}`}
                      aria-label={t('platform.configureNamed', {
                        name: municipality.name,
                      })}
                    >
                      {t('platform.configure')}
                    </Anchor>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Pager {...table.pager} />

      <Paper withBorder p="md">
        <form onSubmit={(event) => void create(event)}>
          <Group align="flex-end" gap="sm">
            <TextInput
              label={t('platform.name')}
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
            <TextInput
              label={t('platform.slug')}
              description={t('platform.slugHint')}
              required
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              maxLength={100}
              value={slug}
              onChange={(event) => setSlug(event.currentTarget.value)}
            />
            <NativeSelect
              label={t('platform.kind')}
              value={kind}
              onChange={(event) => setKind(event.currentTarget.value)}
              data={KINDS.map((value) => ({
                value,
                label: t(`platform.kinds.${value}`),
              }))}
            />
            <Button type="submit" loading={action.pending}>
              {t('platform.add')}
            </Button>
          </Group>
        </form>
      </Paper>
    </Stack>
  )
}
