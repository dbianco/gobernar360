import {
  ActionIcon,
  Alert,
  Badge,
  Group,
  Menu,
  Paper,
  Stack,
  Table,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../authContext'
import { useMonthCommitments } from '../commitments/api'
import { MonthCommitments } from '../commitments/MonthCommitments'
import type { SubjectCommitment } from '../commitments/types'
import { errorMessage } from '../errorMessage'
import { hasLevel } from '../access'
import { useYearValues } from '../indicators/api'
import { formatIndicator, indicatorLabelKey } from '../indicators/format'
import { currentYear } from '../years'
import { useDashboardStatus, useSetStatus } from './api'
import { StatusLight } from './StatusLight'
import { STATUS_COLORS, type StatusColor } from './types'

const MONTHS = Array.from({ length: 12 }, (_, index) => index + 1)
const LIGHT_SIZE = 30

function hasStarted(year: number, month: number): boolean {
  const now = new Date()
  return year * 12 + month <= now.getFullYear() * 12 + now.getMonth() + 1
}

/**
 * The light of each month of a year for one dashboard, with the month's headline
 * indicators under it. Its administrators set the lights here; everyone else only
 * sees them. Below, what was agreed about each month.
 */
export function StatusStrip(props: {
  dashboardKey: string
  year: number
  /** For pages without a year of their own: lets the strip move between years. */
  onYearChange?: (year: number) => void
}) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const status = useDashboardStatus(props.dashboardKey, props.year)
  const change = useSetStatus(props.dashboardKey)
  // The numbers only add to the lights, so a failure to load them leaves the strip as it was.
  const numbers = useYearValues(props.dashboardKey, props.year).data
  const byMonth = new Map(numbers?.months.map((entry) => [entry.month, entry.values]))
  const rows = (numbers?.indicators ?? []).filter((indicator) =>
    numbers?.months.some((entry) => indicator.key in entry.values),
  )
  const canSet = hasLevel(me, props.dashboardKey, 'admin')
  const colors = new Map(status.data?.map((entry) => [entry.month, entry.color]))
  const commitments = useMonthCommitments(props.dashboardKey, props.year)
  const agreed = new Map<number, SubjectCommitment[]>()
  for (const commitment of commitments.data ?? []) {
    const number = Number(commitment.ref.split('-')[1])
    agreed.set(number, [...(agreed.get(number) ?? []), commitment])
  }
  const failed = status.error ?? commitments.error
  const error = change.error ?? (failed ? errorMessage(failed) : null)

  const month = (number: number) => {
    const color: StatusColor | null = colors.get(number) ?? null
    const name = t('status.monthLabel', {
      month: t(`status.months.${number}`),
      state: t(`status.states.${color ?? 'none'}`),
    })
    const caption = (
      <Text size="xs" c="dimmed" aria-hidden>
        {t(`status.monthsShort.${number}`)}
      </Text>
    )
    if (!canSet) {
      return (
        <Stack gap={2} align="center" role="img" aria-label={name} title={name}>
          <StatusLight color={color} size={LIGHT_SIZE} />
          {caption}
        </Stack>
      )
    }
    const started = hasStarted(props.year, number)
    return (
      <Menu position="bottom" withArrow>
        <Menu.Target>
          <UnstyledButton
            aria-label={name}
            title={name}
            disabled={!started || change.pending}
            style={{
              opacity: started ? 1 : 0.45,
              cursor: started ? 'pointer' : 'not-allowed',
            }}
          >
            <Stack gap={2} align="center">
              <StatusLight color={color} size={LIGHT_SIZE} />
              {caption}
            </Stack>
          </UnstyledButton>
        </Menu.Target>
        <Menu.Dropdown>
          {STATUS_COLORS.map((option) => (
            <Menu.Item
              key={option}
              leftSection={<StatusLight color={option} size={18} />}
              onClick={() => void change.set(props.year, number, option)}
            >
              {t(`status.states.${option}`)}
            </Menu.Item>
          ))}
          {color && (
            <>
              <Menu.Divider />
              <Menu.Item onClick={() => void change.set(props.year, number, null)}>
                {t('status.clear')}
              </Menu.Item>
            </>
          )}
        </Menu.Dropdown>
      </Menu>
    )
  }

  return (
    <Paper withBorder p="sm" component="section" aria-label={t('status.title')}>
      <Stack gap="xs">
        <Group gap="xs" align="baseline">
          <Text fw={600} size="sm">
            {`${t('status.title')} ${props.year}`}
          </Text>
          {props.onYearChange && (
            <Group gap={0}>
              <ActionIcon
                variant="subtle"
                size="sm"
                aria-label={t('status.previousYear')}
                onClick={() => props.onYearChange?.(props.year - 1)}
              >
                <IconChevronLeft size={16} aria-hidden />
              </ActionIcon>
              <ActionIcon
                variant="subtle"
                size="sm"
                aria-label={t('status.nextYear')}
                disabled={props.year >= currentYear()}
                onClick={() => props.onYearChange?.(props.year + 1)}
              >
                <IconChevronRight size={16} aria-hidden />
              </ActionIcon>
            </Group>
          )}
          <Text size="xs" c="dimmed">
            {t('status.hint')}
          </Text>
        </Group>
        <Table.ScrollContainer minWidth={rows.length ? 760 : 520} type="native">
          <Table
            withRowBorders={false}
            verticalSpacing={2}
            horizontalSpacing={4}
            aria-label={t('status.tableLabel', { year: props.year })}
          >
            <Table.Thead>
              <Table.Tr>
                {rows.length > 0 && (
                  <Table.Th fw={400}>
                    <Text size="xs" c="dimmed">
                      {t('status.numbers')}
                    </Text>
                  </Table.Th>
                )}
                {MONTHS.map((number) => (
                  <Table.Th key={number} ta="center" fw={400}>
                    <Group justify="center">
                      <div style={{ position: 'relative' }}>
                        {month(number)}
                        {agreed.has(number) && (
                          // How many are listed below, at a glance.
                          <Badge
                            circle
                            size="sm"
                            aria-hidden
                            style={{
                              position: 'absolute',
                              top: -6,
                              right: -8,
                              pointerEvents: 'none',
                            }}
                          >
                            {agreed.get(number)?.length}
                          </Badge>
                        )}
                      </div>
                    </Group>
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            {rows.length > 0 && (
              <Table.Tbody>
                {rows.map((indicator) => (
                  <Table.Tr key={indicator.key}>
                    <Table.Th scope="row" fw={400}>
                      <Text size="xs" lineClamp={1} title={t(indicatorLabelKey(indicator.key))}>
                        {t(indicatorLabelKey(indicator.key))}
                      </Text>
                    </Table.Th>
                    {MONTHS.map((number) => {
                      const values = byMonth.get(number) ?? {}
                      return (
                        <Table.Td key={number} ta="center">
                          <Text size="xs">
                            {indicator.key in values
                              ? formatIndicator(values[indicator.key], indicator.unit)
                              : ''}
                          </Text>
                        </Table.Td>
                      )
                    })}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            )}
          </Table>
        </Table.ScrollContainer>
        {error && <Alert color="red">{error}</Alert>}
        {agreed.size > 0 && <MonthCommitments byMonth={agreed} colors={colors} />}
      </Stack>
    </Paper>
  )
}
