import { Alert, Group, Menu, Paper, Stack, Text, UnstyledButton } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../authContext'
import { errorMessage } from '../errorMessage'
import { hasLevel } from '../types'
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
 * The light of each month of a year for one dashboard. Its administrators set
 * them here; everyone else only sees them.
 */
export function StatusStrip(props: { dashboardKey: string; year: number }) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const status = useDashboardStatus(props.dashboardKey, props.year)
  const change = useSetStatus(props.dashboardKey)
  const canSet = hasLevel(me, props.dashboardKey, 'admin')
  const colors = new Map(status.data?.map((entry) => [entry.month, entry.color]))
  const error = change.error ?? (status.isError ? errorMessage(status.error) : null)

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
          <Text size="xs" c="dimmed">
            {t('status.hint')}
          </Text>
        </Group>
        <Group gap="md" role="list">
          {MONTHS.map((number) => (
            <div key={number} role="listitem">
              {month(number)}
            </div>
          ))}
        </Group>
        {error && <Alert color="red">{error}</Alert>}
      </Stack>
    </Paper>
  )
}
