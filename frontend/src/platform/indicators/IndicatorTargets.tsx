import { Alert, Button, Group, Loader, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../errorMessage'
import { HelpTh } from '../HelpTh'
import { YearSelect } from '../YearSelect'
import { currentYear } from '../years'
import { useSetTarget, useTargets } from './api'
import { indicatorLabelKey } from './format'
import type { IndicatorTarget, IndicatorUnit } from './types'

/** Ratios are typed as percentages: a target of 0.6 is entered as 60. */
const toInput = (value: number | null, unit: IndicatorUnit): string =>
  value === null ? '' : String(unit === 'ratio' ? Math.round(value * 1e6) / 1e4 : value)

function fromInput(text: string, unit: IndicatorUnit): number | null {
  if (text.trim() === '') return null
  const value = Number(text)
  return unit === 'ratio' ? value / 100 : value
}

function TargetRow(props: {
  item: IndicatorTarget
  year: number
  label: string
  pending: boolean
  onSave: (value: number | null) => void
}) {
  const { t } = useTranslation()
  const { item } = props
  const [text, setText] = useState(toInput(item.target, item.unit))
  const value = fromInput(text, item.unit)
  const changed = value !== item.target && !(value !== null && Number.isNaN(value))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (changed) props.onSave(value)
  }

  return (
    <Table.Tr>
      <Table.Th scope="row" fw={400}>
        {props.label}
      </Table.Th>
      <Table.Td>
        {t(
          item.higher_is_better
            ? 'indicators.detail.higherIsBetter'
            : 'indicators.detail.lowerIsBetter',
        )}
      </Table.Td>
      <Table.Td>
        <form onSubmit={submit}>
          <Group gap="xs" wrap="nowrap">
            <TextInput
              aria-label={t('indicators.targets.inputLabel', {
                name: props.label,
                year: props.year,
              })}
              type="number"
              step="any"
              w={140}
              value={text}
              onChange={(event) => setText(event.currentTarget.value)}
              rightSection={item.unit ? <Text size="xs">%</Text> : null}
            />
            <Button type="submit" size="xs" variant="light" disabled={!changed || props.pending}>
              {t('indicators.targets.save')}
            </Button>
          </Group>
        </form>
      </Table.Td>
    </Table.Tr>
  )
}

/**
 * The targets of a dashboard's headline indicators, one per indicator and year. For its
 * administrators, in the dashboard's parameters.
 */
export function IndicatorTargets(props: { dashboardKey: string }) {
  const { t } = useTranslation()
  const [year, setYear] = useState(currentYear)
  const targets = useTargets(props.dashboardKey, year)
  const change = useSetTarget(props.dashboardKey)
  const label = (key: string, options = {}) => t(`indicators.targets.${key}`, options)

  return (
    <Stack gap="sm" component="section" aria-label={label('title')}>
      <Title order={4}>{label('title')}</Title>
      <Text size="sm" c="dimmed">
        {label('hint')}
      </Text>
      <Group>
        <YearSelect value={year} onChange={setYear} />
      </Group>
      {change.error && (
        <Alert color="red" withCloseButton onClose={change.clearError}>
          {change.error}
        </Alert>
      )}
      {targets.isError && <Alert color="red">{errorMessage(targets.error)}</Alert>}
      {targets.isLoading && <Loader size="sm" aria-label={t('app.loading')} />}
      {targets.data && (
        <Table.ScrollContainer minWidth={560}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={label('help.indicator')}>{label('indicator')}</HelpTh>
                <HelpTh help={label('help.direction')}>{label('direction')}</HelpTh>
                <HelpTh help={label('help.target')}>{label('target', { year })}</HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {targets.data.map((item) => (
                <TargetRow
                  key={`${year}/${item.key}/${item.target}`}
                  item={item}
                  year={year}
                  label={t(indicatorLabelKey(item.key))}
                  pending={change.pending}
                  onSave={(value) => void change.set(year, item.key, value)}
                />
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
