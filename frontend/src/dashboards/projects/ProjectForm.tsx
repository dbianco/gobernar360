import {
  Alert,
  Button,
  Checkbox,
  Fieldset,
  Group,
  NativeSelect,
  SimpleGrid,
  Stack,
  Textarea,
  TextInput,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import { errorMessage } from '../../platform/errorMessage'
import { PersonSelect } from '../../platform/PersonSelect'
import {
  send,
  useAction,
  useAxes,
  useDepartments,
  useObjectives,
  useOwners,
  usePrograms,
} from './api'
import { termYears, useTerm } from './termContext'
import {
  PRIORITIES,
  type Project,
  type ProjectInput,
  SDG_NUMBERS,
  STORED_STATUSES,
} from './types'

function initialValues(project: Project | undefined, defaultYear: number): ProjectInput {
  return {
    name: project?.name ?? '',
    description: project?.description ?? '',
    axis_id: project?.axis.id ?? '',
    objective_id: project?.objective?.id ?? null,
    department_id: project?.department.id ?? '',
    owner_id: project?.owner?.id ?? null,
    program_id: project?.program?.id ?? null,
    priority: project?.priority ?? 'A',
    year: project?.year ?? defaultYear,
    start_date: project?.start_date ?? null,
    end_date: project?.end_date ?? null,
    planned_budget: project?.planned_budget ?? '0',
    executed_budget: project?.executed_budget ?? '0',
    status: project?.status ?? 'not_started',
    manual_progress: project?.manual_progress ?? null,
    sdgs: project?.sdgs ?? [],
  }
}

/** Create a project in the current term, or edit an existing one. */
export function ProjectForm(props: {
  project?: Project
  onSaved: (project: Project) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const { term: selectedTerm, terms } = useTerm()
  // An existing project is edited within its own term, whichever term is on screen.
  const term = terms.find((candidate) => candidate.id === props.project?.term_id) ?? selectedTerm
  const years = termYears(term)
  const [values, setValues] = useState<ProjectInput>(() => {
    const thisYear = new Date().getFullYear()
    return initialValues(props.project, years.includes(thisYear) ? thisYear : term.start_year)
  })
  const axes = useAxes(term.id)
  const objectives = useObjectives(term.id)
  const departments = useDepartments()
  const owners = useOwners()
  const programs = usePrograms()
  const action = useAction()
  const catalogError = [axes, objectives, departments, owners, programs].find((q) => q.isError)

  const set = <K extends keyof ProjectInput>(field: K, value: ProjectInput[K]) =>
    setValues((current) => ({ ...current, [field]: value }))
  const label = (key: string) => t(`projects.form.${key}`)
  const named = (items?: { id: string; name: string }[]) =>
    (items ?? []).map((item) => ({ value: item.id, label: item.name }))
  const choose = { value: '', label: label('choose') }
  const unassigned = { value: '', label: label('unassigned') }
  // Manual progress only applies while the project has no milestones.
  const showManualProgress = !props.project || props.project.milestones.length === 0

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { ...values, sdgs: [...values.sdgs].sort((a, b) => a - b) }
    const saved = await action.run(() =>
      props.project
        ? send<Project>('PATCH', `/projects/${props.project.id}`, body)
        : send<Project>('POST', '/projects', { ...body, term_id: term.id }),
    )
    if (saved) props.onSaved(saved)
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {catalogError && <Alert color="red">{errorMessage(catalogError.error)}</Alert>}
        <TextInput
          label={label('name')}
          required
          maxLength={200}
          value={values.name}
          onChange={(event) => set('name', event.currentTarget.value)}
        />
        <Textarea
          label={label('description')}
          rows={3}
          value={values.description}
          onChange={(event) => set('description', event.currentTarget.value)}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NativeSelect
            label={label('axis')}
            required
            value={values.axis_id}
            onChange={(event) => {
              // Read now: the event is gone by the time the state updater runs.
              const axisId = event.currentTarget.value
              // The objective belongs to the axis, so changing the axis clears it.
              setValues((current) => ({ ...current, axis_id: axisId, objective_id: null }))
            }}
            data={[choose, ...named(axes.data)]}
          />
          <NativeSelect
            label={label('objective')}
            value={values.objective_id ?? ''}
            onChange={(event) => set('objective_id', event.currentTarget.value || null)}
            data={[
              unassigned,
              ...named(objectives.data?.filter((o) => o.axis_id === values.axis_id)),
            ]}
          />
          <NativeSelect
            label={label('department')}
            required
            value={values.department_id}
            onChange={(event) => set('department_id', event.currentTarget.value)}
            data={[choose, ...named(departments.data)]}
          />
          <PersonSelect
            label={label('owner')}
            placeholder={label('unassigned')}
            value={values.owner_id ?? ''}
            onChange={(id) => set('owner_id', id || null)}
            people={owners.data ?? []}
          />
          <NativeSelect
            label={label('program')}
            value={values.program_id ?? ''}
            onChange={(event) => set('program_id', event.currentTarget.value || null)}
            data={[unassigned, ...named(programs.data)]}
          />
          <NativeSelect
            label={label('priority')}
            value={values.priority}
            onChange={(event) => set('priority', event.currentTarget.value as never)}
            data={PRIORITIES}
          />
          <NativeSelect
            label={label('year')}
            value={String(values.year)}
            onChange={(event) => set('year', Number(event.currentTarget.value))}
            data={years.map(String)}
          />
          <NativeSelect
            label={label('status')}
            value={values.status}
            onChange={(event) => set('status', event.currentTarget.value as never)}
            data={STORED_STATUSES.map((status) => ({
              value: status,
              label: t(`projects.status.${status}`),
            }))}
          />
          <DateField
            label={label('startDate')}
            value={values.start_date ?? ''}
            onChange={(date) => set('start_date', date || null)}
          />
          <DateField
            label={label('endDate')}
            min={values.start_date}
            value={values.end_date ?? ''}
            onChange={(date) => set('end_date', date || null)}
          />
          <TextInput
            label={label('plannedBudget')}
            type="number"
            min={0}
            step="0.01"
            required
            value={values.planned_budget}
            onChange={(event) => set('planned_budget', event.currentTarget.value)}
          />
          <TextInput
            label={label('executedBudget')}
            type="number"
            min={0}
            step="0.01"
            required
            value={values.executed_budget}
            onChange={(event) => set('executed_budget', event.currentTarget.value)}
          />
          {showManualProgress && (
            <TextInput
              label={label('manualProgress')}
              description={label('manualProgressHint')}
              type="number"
              min={0}
              max={100}
              step={1}
              value={values.manual_progress ?? ''}
              onChange={(event) =>
                set(
                  'manual_progress',
                  event.currentTarget.value === '' ? null : Number(event.currentTarget.value),
                )
              }
            />
          )}
        </SimpleGrid>
        <Fieldset legend={label('sdgs')}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
            {SDG_NUMBERS.map((number) => (
              <Checkbox
                key={number}
                label={t('projects.sdgLabel', { number, title: t(`projects.sdg.${number}`) })}
                checked={values.sdgs.includes(number)}
                onChange={(event) =>
                  set(
                    'sdgs',
                    event.currentTarget.checked
                      ? [...values.sdgs, number]
                      : values.sdgs.filter((sdg) => sdg !== number),
                  )
                }
              />
            ))}
          </SimpleGrid>
        </Fieldset>
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onCancel}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
