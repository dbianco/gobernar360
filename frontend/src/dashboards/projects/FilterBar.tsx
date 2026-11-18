import { Alert, Group, NativeSelect } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { useAxes, useDepartments, useOwners } from './api'
import { termYears, useTerm } from './termContext'
import { EFFECTIVE_STATUSES, PRIORITIES, type ProjectFilters } from './types'

interface Option {
  value: string
  label: string
}

/** One row of filters shared by the summary and the project list. */
export function FilterBar(props: {
  filters: ProjectFilters
  onChange: (filters: ProjectFilters) => void
  withStatus?: boolean
}) {
  const { t } = useTranslation()
  const { term } = useTerm()
  const axes = useAxes(term.id)
  const departments = useDepartments()
  const owners = useOwners()

  const select = (field: keyof ProjectFilters, label: string, options: Option[]) => (
    <NativeSelect
      label={label}
      value={props.filters[field] ?? ''}
      onChange={(event) =>
        props.onChange({ ...props.filters, [field]: event.currentTarget.value || undefined })
      }
      data={[{ value: '', label: t('app.all') }, ...options]}
    />
  )
  const named = (items?: { id: string; name: string }[]) =>
    (items ?? []).map((item) => ({ value: item.id, label: item.name }))

  const failed = [axes, departments, owners].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>

  return (
    <Group align="flex-end" gap="sm">
      {select(
        'year',
        t('projects.filters.year'),
        termYears(term).map((year) => ({ value: String(year), label: String(year) })),
      )}
      {select('axis_id', t('projects.filters.axis'), named(axes.data))}
      {select('department_id', t('projects.filters.department'), named(departments.data))}
      {select(
        'owner_id',
        t('projects.filters.owner'),
        (owners.data ?? []).map((owner) => ({ value: owner.id, label: owner.full_name })),
      )}
      {select(
        'priority',
        t('projects.filters.priority'),
        PRIORITIES.map((priority) => ({ value: priority, label: priority })),
      )}
      {props.withStatus &&
        select(
          'status',
          t('projects.filters.status'),
          EFFECTIVE_STATUSES.map((status) => ({
            value: status,
            label: t(`projects.status.${status}`),
          })),
        )}
    </Group>
  )
}
