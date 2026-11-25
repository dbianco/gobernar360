import { Alert, Group, NativeSelect, Select, Stack } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { dashboardLabelKey } from '../../dashboards/registry'
import { errorMessage } from '../errorMessage'
import { useSubjectKinds, useSubjectSearch } from './api'
import { MONTH, refOf, type Subject, type SubjectKind, type SubjectRef } from './types'

const SEARCH_DELAY = 200
const kindValue = (kind: SubjectKind) => `${kind.dashboard_key}/${kind.kind}`

/**
 * Chooses what to link to: first the kind (a month of a dashboard, a project...), then
 * which one. It knows no dashboard: kinds and their records come from the API.
 */
export function SubjectPicker(props: {
  /** What was linked when the form opened. */
  initial?: Subject | null
  onChange: (value: SubjectRef | null) => void
}) {
  const { t } = useTranslation()
  const kinds = useSubjectKinds()
  const initial = refOf(props.initial) ? props.initial! : null
  const [kind, setKind] = useState<SubjectKind | null>(
    initial && { dashboard_key: initial.dashboard_key!, kind: initial.kind },
  )
  const [chosen, setChosen] = useState<Subject | null>(initial)
  const [typed, setTyped] = useState('')
  const [q] = useDebouncedValue(typed, SEARCH_DELAY)
  // The box shows the name of what is chosen, which is not a search.
  const found = useSubjectSearch(kind, q === chosen?.label ? '' : q)
  const error = kinds.error ?? found.error

  function chooseKind(value: string) {
    const next = kinds.data?.find((option) => kindValue(option) === value) ?? null
    setKind(next)
    setChosen(null)
    setTyped('')
    props.onChange(null)
  }

  function choose(ref: string | null) {
    const next = found.data?.find((option) => option.ref === ref) ?? null
    setChosen(next)
    props.onChange(refOf(next))
  }

  // What is chosen stays an option when the search no longer finds it.
  const options = (found.data ?? []).filter((option) => option.kind === kind?.kind)
  const offered =
    chosen && !options.some((option) => option.ref === chosen.ref) ? [chosen, ...options] : options
  const dashboardName = (key: string) => {
    const labelKey = dashboardLabelKey(key)
    return labelKey ? t(labelKey) : key
  }

  return (
    <Stack gap="xs">
      {error && <Alert color="red">{errorMessage(error)}</Alert>}
      <Group grow align="flex-start" preventGrowOverflow={false}>
        <NativeSelect
          label={t('subjects.about')}
          value={kind ? kindValue(kind) : ''}
          onChange={(event) => chooseKind(event.currentTarget.value)}
          data={[
            { value: '', label: t('subjects.none') },
            ...(kinds.data ?? []).map((option) => ({
              value: kindValue(option),
              label: t('subjects.kindOf', {
                dashboard: dashboardName(option.dashboard_key),
                kind: t([
                  `subjects.kinds.${option.dashboard_key}.${option.kind}`,
                  `subjects.kinds.${option.kind === MONTH ? 'month' : 'record'}`,
                ]),
              }),
            })),
          ]}
        />
        {kind && (
          <Select
            label={t('subjects.which')}
            placeholder={t('subjects.searchHint')}
            nothingFoundMessage={found.isFetching ? t('app.loading') : t('app.noMatches')}
            searchable
            clearable
            required
            withAsterisk={false}
            data={offered.map((option) => ({
              value: option.ref!,
              label: option.color
                ? t('subjects.withState', {
                    label: option.label,
                    state: t(`status.states.${option.color}`),
                  })
                : option.label!,
            }))}
            // The API already searched.
            filter={({ options: all }) => all}
            value={chosen?.ref ?? null}
            onChange={choose}
            onSearchChange={setTyped}
          />
        )}
      </Group>
    </Stack>
  )
}
