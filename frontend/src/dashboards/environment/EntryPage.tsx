import { Alert, Group, Loader, NativeSelect, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { send, useAction, useValues, useVariables } from './api'
import { CATEGORIES, type Category, MONTHS, type Variable, WHOLE_YEAR } from './types'
import { currentYear } from './years'
import { YearSelect } from './YearSelect'

const NUMBER = /^-?\d+([.,]\d{1,4})?$/

/** Numbers are shown and typed with a decimal comma; the API uses a dot. */
const shown = (value: number | undefined) => (value === undefined ? '' : String(value).replace('.', ','))

/**
 * One period of one variable. It saves when the person leaves the cell, and only if the
 * text changed; an empty cell removes the value.
 */
function Cell(props: {
  label: string
  value: number | undefined
  onSave: (value: string | null) => Promise<boolean>
}) {
  const stored = shown(props.value)
  // null while the cell shows what is stored; text while it holds an unsaved edit.
  const [draft, setDraft] = useState<string | null>(null)
  const [invalid, setInvalid] = useState(false)

  async function commit() {
    if (draft === null) return
    const text = draft.trim()
    if (text === stored) {
      setDraft(null)
      setInvalid(false)
      return
    }
    if (text !== '' && !NUMBER.test(text)) {
      setInvalid(true)
      return
    }
    const saved = await props.onSave(text === '' ? null : text.replace(',', '.'))
    setInvalid(!saved)
    if (saved) setDraft(null)
  }

  return (
    <TextInput
      aria-label={props.label}
      aria-invalid={invalid}
      error={invalid}
      size="xs"
      inputMode="decimal"
      miw={76}
      value={draft ?? stored}
      onChange={(event) => setDraft(event.currentTarget.value)}
      onBlur={() => void commit()}
    />
  )
}

/** Grid where the values of a year are loaded, one row per variable. */
export function EntryPage() {
  const { t } = useTranslation()
  const [year, setYear] = useState(currentYear)
  const [category, setCategory] = useState<Category | ''>('')
  const variables = useVariables()
  const values = useValues(year)
  const action = useAction()
  const label = (key: string) => t(`environment.entry.${key}`)

  const failed = [variables, values].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>

  const stored = new Map(
    (values.data ?? []).map((value) => [`${value.variable_id}:${value.period}`, value.value]),
  )
  const visible = (variables.data ?? []).filter(
    (variable) => category === '' || variable.subcategory.category === category,
  )
  const monthly = visible.filter((variable) => variable.frequency === 'monthly')
  const annual = visible.filter((variable) => variable.frequency === 'annual')

  const cell = (variable: Variable, period: number) => (
    <Cell
      // Keyed by year so an unsaved edit never carries over to another year.
      key={`${variable.id}:${period}:${year}`}
      label={t('environment.entry.cell', {
        variable: variable.name,
        period: period === WHOLE_YEAR ? year : t(`environment.monthNames.${period}`),
      })}
      value={stored.get(`${variable.id}:${period}`)}
      onSave={async (value) =>
        (await action.run(async () => {
          await send('PUT', '/values', { variable_id: variable.id, year, period, value })
          return true
        })) ?? false
      }
    />
  )
  const nameCell = (variable: Variable) => (
    <Table.Th scope="row" fw={400} miw={220}>
      <Text size="sm">{variable.name}</Text>
      <Text size="xs" c="dimmed">
        {[variable.subcategory.name, variable.unit].filter(Boolean).join(' · ')}
      </Text>
    </Table.Th>
  )

  return (
    <Stack>
      <Group align="flex-end">
        <YearSelect value={year} onChange={setYear} />
        <NativeSelect
          label={label('category')}
          value={category}
          onChange={(event) => setCategory(event.currentTarget.value as Category | '')}
          data={[
            { value: '', label: t('app.all') },
            ...CATEGORIES.map((value) => ({
              value,
              label: t(`environment.categories.${value}`),
            })),
          ]}
        />
      </Group>
      <Text size="sm" c="dimmed">
        {label('hint')}
      </Text>
      {action.error && <Alert color="red">{action.error}</Alert>}
      {(variables.isLoading || values.isLoading) && <Loader aria-label={t('app.loading')} />}
      {variables.data && values.data && visible.length === 0 && (
        <Text c="dimmed">{label('empty')}</Text>
      )}
      {values.data && monthly.length > 0 && (
        <Stack gap="xs" component="section">
          <Title order={4}>{label('monthly')}</Title>
          <Table.ScrollContainer minWidth={1240}>
            <Table verticalSpacing={4} horizontalSpacing={4}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{label('variable')}</Table.Th>
                  {MONTHS.map((month) => (
                    <Table.Th key={month}>{t(`environment.monthsShort.${month}`)}</Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {monthly.map((variable) => (
                  <Table.Tr key={variable.id}>
                    {nameCell(variable)}
                    {MONTHS.map((month) => (
                      <Table.Td key={month}>{cell(variable, month)}</Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Stack>
      )}
      {values.data && annual.length > 0 && (
        <Stack gap="xs" component="section">
          <Title order={4}>{label('annual')}</Title>
          <Table verticalSpacing={4} maw={480}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{label('variable')}</Table.Th>
                <Table.Th>{year}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {annual.map((variable) => (
                <Table.Tr key={variable.id}>
                  {nameCell(variable)}
                  <Table.Td>{cell(variable, WHOLE_YEAR)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}
    </Stack>
  )
}
