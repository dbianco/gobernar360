import { Alert, Group, Loader, NativeSelect, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { formatNumber } from '../../platform/format'
import { useSeries, useSubcategories, useVariables } from './api'
import { SeriesChart, type SeriesPoint } from './SeriesChart'
import { CATEGORIES, type Category, type Series } from './types'
import { currentYear } from './years'
import { YearSelect } from './YearSelect'

type View = 'monthly' | 'annual'

/** How one variable evolved: month by month in a year, or year by year. */
export function TrackingPage() {
  const { t } = useTranslation()
  const subcategories = useSubcategories()
  const variables = useVariables()
  const [category, setCategory] = useState<Category | ''>('')
  const [subcategoryId, setSubcategoryId] = useState('')
  const [variableId, setVariableId] = useState('')
  const [year, setYear] = useState(currentYear)
  const [chosenView, setChosenView] = useState<View>('monthly')
  const label = (key: string) => t(`environment.tracking.${key}`)

  const offeredSubcategories = (subcategories.data ?? []).filter(
    (item) => category === '' || item.category === category,
  )
  const offered = (variables.data ?? []).filter(
    (item) =>
      (category === '' || item.subcategory.category === category) &&
      (subcategoryId === '' || item.subcategory.id === subcategoryId),
  )
  // Narrowing the filters can leave the chosen variable out; fall back to the first one.
  const variable = offered.find((item) => item.id === variableId) ?? offered[0]
  const view: View = variable?.frequency === 'annual' ? 'annual' : chosenView
  const series = useSeries(variable?.id ?? '', year)

  const failed = [subcategories, variables].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (!subcategories.data || !variables.data) return <Loader aria-label={t('app.loading')} />
  if (variables.data.length === 0) return <Text c="dimmed">{label('empty')}</Text>

  const points = (data: Series): SeriesPoint[] =>
    view === 'monthly'
      ? data.monthly.map((point) => ({
          label: t(`environment.monthsShort.${point.period}`),
          name: t(`environment.monthNames.${point.period}`),
          value: point.value,
        }))
      : data.annual.map((point) => ({
          label: String(point.year),
          name: String(point.year),
          value: point.value,
        }))
  // A yearly target says nothing about one month of a variable that adds its months up.
  const comparable = (data: Series) =>
    view === 'annual' || data.variable.annual_aggregation !== 'sum'
  const yearFigure = series.data?.annual.find((point) => point.year === year)

  return (
    <Stack>
      <Group align="flex-end" gap="sm">
        <NativeSelect
          label={label('category')}
          value={category}
          onChange={(event) => {
            setCategory(event.currentTarget.value as Category | '')
            setSubcategoryId('')
          }}
          data={[
            { value: '', label: t('app.all') },
            ...CATEGORIES.map((value) => ({
              value,
              label: t(`environment.categories.${value}`),
            })),
          ]}
        />
        <NativeSelect
          label={label('subcategory')}
          value={subcategoryId}
          onChange={(event) => setSubcategoryId(event.currentTarget.value)}
          data={[
            { value: '', label: t('app.all') },
            ...offeredSubcategories.map((item) => ({ value: item.id, label: item.name })),
          ]}
        />
        <NativeSelect
          label={label('variable')}
          value={variable?.id ?? ''}
          onChange={(event) => setVariableId(event.currentTarget.value)}
          data={offered.map((item) => ({ value: item.id, label: item.name }))}
        />
        <NativeSelect
          label={label('view')}
          value={view}
          disabled={variable?.frequency === 'annual'}
          onChange={(event) => setChosenView(event.currentTarget.value as View)}
          data={[
            { value: 'monthly', label: label('monthly') },
            { value: 'annual', label: label('annual') },
          ]}
        />
        {view === 'monthly' && <YearSelect value={year} onChange={setYear} />}
      </Group>
      {!variable && <Text c="dimmed">{label('noMatch')}</Text>}
      {variable && series.isLoading && <Loader aria-label={t('app.loading')} />}
      {variable && series.isError && <Alert color="red">{errorMessage(series.error)}</Alert>}
      {variable && series.data && (
        <>
          <SeriesChart
            title={
              view === 'monthly'
                ? t('environment.tracking.titleMonthly', { variable: variable.name, year })
                : t('environment.tracking.titleAnnual', { variable: variable.name })
            }
            unit={variable.unit}
            points={points(series.data)}
            target={comparable(series.data) ? variable.target : null}
            periodHeader={label(view === 'monthly' ? 'month' : 'yearColumn')}
          />
          {view === 'monthly' && yearFigure && (
            <Text size="sm" c="dimmed">
              {t('environment.tracking.yearFigure', {
                year,
                value: `${formatNumber(yearFigure.value, 2)} ${variable.unit}`.trim(),
                how: t(`environment.aggregations.${variable.annual_aggregation}`).toLowerCase(),
              })}
              {variable.target !== null &&
                ` ${t('environment.tracking.yearTarget', {
                  target: `${formatNumber(variable.target, 2)} ${variable.unit}`.trim(),
                })}`}
            </Text>
          )}
        </>
      )}
    </Stack>
  )
}
