import {
  Alert,
  Anchor,
  Badge,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber, formatRatio } from '../../platform/format'
import { HeadlineIndicators } from '../../platform/indicators/HeadlineIndicators'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { hasLevel } from '../../platform/types'
import { BASE, BASE_PATH, useSummary } from './api'
import type { CategorySummary, VariableSummary } from './types'
import { currentYear } from './years'
import { YearSelect } from './YearSelect'

/** "2.500 / 12.000 kWh": the year's figure, its target when there is one, and the unit. */
function valueText(row: VariableSummary): string {
  if (row.value === null) return formatNumber(null)
  const { target, unit } = row.variable
  const figure = formatNumber(row.value, 2)
  const text = target === null ? figure : `${figure} / ${formatNumber(target, 2)}`
  return unit ? `${text} ${unit}` : text
}

function CategoryTable({ category }: { category: CategorySummary }) {
  const { t } = useTranslation()
  const label = (key: string) => t(`environment.summary.${key}`)

  return (
    <Stack gap="xs" component="section">
      <Group justify="space-between" align="baseline">
        <Title order={4}>{t(`environment.categories.${category.category}`)}</Title>
        <Text size="sm" c="dimmed">
          {t('environment.summary.categoryLoads', {
            loaded: category.loaded,
            expected: category.expected,
          })}
        </Text>
      </Group>
      <Table.ScrollContainer minWidth={640}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <HelpTh help={t('environment.help.summaryPage.variable')}>{label('variable')}</HelpTh>
              <HelpTh help={t('environment.help.summaryPage.subcategory')}>
                {label('subcategory')}
              </HelpTh>
              <HelpTh help={t('environment.help.summaryPage.value')}>{label('value')}</HelpTh>
              <HelpTh help={t('environment.help.summaryPage.achievement')}>
                {label('achievement')}
              </HelpTh>
              <HelpTh help={t('environment.help.summaryPage.loadsColumn')}>
                {label('loadsColumn')}
              </HelpTh>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {category.variables.map((row) => (
              <Table.Tr key={row.variable.id}>
                <Table.Td>{row.variable.name}</Table.Td>
                <Table.Td>{row.variable.subcategory.name}</Table.Td>
                <Table.Td>{valueText(row)}</Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <span>{formatRatio(row.achievement)}</span>
                    {row.target_met !== null && (
                      <Badge variant="light" color={row.target_met ? 'green' : 'orange'}>
                        {label(row.target_met ? 'met' : 'missed')}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>{`${row.loaded} / ${row.expected}`}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  )
}

/** Where every variable stands in the chosen year, grouped by category. */
export function SummaryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [year, setYear] = useState(currentYear)
  const summary = useSummary(year)
  const data = summary.data
  const label = (key: string) => t(`environment.summary.${key}`)
  const used = data?.categories.filter((category) => category.variables.length > 0) ?? []
  const unused = data?.categories.filter((category) => category.variables.length === 0) ?? []

  return (
    <Stack>
      <StatusStrip dashboardKey="environment" year={year} />
      <HeadlineIndicators dashboardKey="environment" />
      <Group align="flex-end" gap="lg">
        <YearSelect value={year} onChange={setYear} />
        <Anchor href={downloadUrl(`${BASE}/export/values.csv`, { year })}>
          {label('download')}
        </Anchor>
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data && data.variable_count === 0 && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{label('emptyTitle')}</Title>
          {hasLevel(me, 'environment', 'admin') ? (
            <Anchor component={Link} to={`${BASE_PATH}/parameters`}>
              {label('goToParameters')}
            </Anchor>
          ) : (
            <Text c="dimmed">{label('emptyViewerBody')}</Text>
          )}
        </Stack>
      )}
      {data && data.variable_count > 0 && (
        <>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            <StatCard label={label('variables')} value={data.variable_count} />
            <StatCard
              label={label('loads')}
              value={`${data.loaded} / ${data.expected}`}
              hint={label('loadsHint')}
            />
            <StatCard label={label('targetsMet')} value={data.targets_met} />
            <StatCard label={label('targetsMissed')} value={data.targets_missed} />
          </SimpleGrid>
          {used.map((category) => (
            <CategoryTable key={category.category} category={category} />
          ))}
          {unused.length > 0 && (
            <Text c="dimmed">
              {`${label('withoutVariables')} ${unused
                .map((category) => t(`environment.categories.${category.category}`))
                .join(', ')}.`}
            </Text>
          )}
        </>
      )}
    </Stack>
  )
}
