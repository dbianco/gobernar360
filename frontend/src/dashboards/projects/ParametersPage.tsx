import {
  Alert,
  Box,
  Button,
  Group,
  Loader,
  NativeSelect,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { EditableList, type ListItem } from '../../platform/EditableList'
import { errorMessage } from '../../platform/errorMessage'
import { IndicatorTargets } from '../../platform/indicators/IndicatorTargets'
import {
  send,
  useAction,
  useAxes,
  useBudgets,
  useDepartments,
  useObjectives,
  useOwners,
  usePrograms,
  useTerms,
} from './api'
import { latestTerm, termYears } from './termContext'
import type { Term } from './types'

type Run = ReturnType<typeof useAction>['run']

/** A flat catalog (departments, programs, owners) stored under `path` with one name field. */
function Catalog(props: { path: string; field: 'name' | 'full_name'; items: ListItem[]; run: Run }) {
  const { t } = useTranslation()
  const { path, field, run } = props
  return (
    <EditableList
      items={props.items}
      addLabel={t('projects.parameters.newItem')}
      onAdd={(name) => run(() => send('POST', path, { [field]: name }))}
      onRename={(item, name) => run(() => send('PATCH', `${path}/${item.id}`, { [field]: name }))}
      onDelete={(item) => run(() => send('DELETE', `${path}/${item.id}`))}
    />
  )
}

function BudgetInput({ term, year, amount, run }: { term: Term; year: number; amount: string; run: Run }) {
  const { t } = useTranslation()
  const [value, setValue] = useState(amount)
  return (
    <TextInput
      label={t('projects.parameters.budgetFor', { year })}
      type="number"
      min={0}
      step="0.01"
      value={value}
      onChange={(event) => setValue(event.currentTarget.value)}
      // Saved when the field loses focus, only if it changed.
      onBlur={() => {
        if (value !== '' && Number(value) !== Number(amount || NaN)) {
          void run(() => send('PUT', `/terms/${term.id}/budgets`, { year, total_amount: value }))
        }
      }}
    />
  )
}

function TermsTab({ terms, selected, run }: { terms: Term[]; selected?: Term; run: Run }) {
  const { t } = useTranslation()
  const budgets = useBudgets(selected?.id)
  const [name, setName] = useState('')
  const [startYear, setStartYear] = useState('')
  const [endYear, setEndYear] = useState('')
  const label = (key: string) => t(`projects.parameters.${key}`)

  async function add(event: FormEvent) {
    event.preventDefault()
    const created = await run(() =>
      send('POST', '/terms', {
        name: name.trim(),
        start_year: Number(startYear),
        end_year: Number(endYear),
      }),
    )
    if (created) {
      setName('')
      setStartYear('')
      setEndYear('')
    }
  }

  return (
    <Stack>
      <EditableList
        items={terms}
        addLabel={label('newItem')}
        onRename={(item, newName) => run(() => send('PATCH', `/terms/${item.id}`, { name: newName }))}
        onDelete={(item) => run(() => send('DELETE', `/terms/${item.id}`))}
      />
      <form onSubmit={(event) => void add(event)}>
        <Group align="flex-end" gap="sm">
          <TextInput
            label={label('name')}
            withAsterisk={false}
            required
            maxLength={200}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
          />
          <TextInput
            label={label('startYear')}
            withAsterisk={false}
            required
            type="number"
            w={130}
            value={startYear}
            onChange={(event) => setStartYear(event.currentTarget.value)}
          />
          <TextInput
            label={label('endYear')}
            withAsterisk={false}
            required
            type="number"
            w={130}
            min={startYear || undefined}
            value={endYear}
            onChange={(event) => setEndYear(event.currentTarget.value)}
          />
          <Button type="submit" variant="default">
            {label('addTerm')}
          </Button>
        </Group>
      </form>
      {budgets.isError && <Alert color="red">{errorMessage(budgets.error)}</Alert>}
      {selected && budgets.data && (
        <Stack gap="xs">
          <Title order={5}>
            {label('budgets')} · {selected.name}
          </Title>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
            {termYears(selected).map((year) => {
              const amount = budgets.data.find((b) => b.year === year)?.total_amount ?? ''
              return (
                <BudgetInput
                  key={`${selected.id}-${year}-${amount}`}
                  term={selected}
                  year={year}
                  amount={amount}
                  run={run}
                />
              )
            })}
          </SimpleGrid>
        </Stack>
      )}
    </Stack>
  )
}

function AxesTab({ term, run }: { term?: Term; run: Run }) {
  const { t } = useTranslation()
  const axes = useAxes(term?.id)
  const objectives = useObjectives(term?.id)
  const label = (key: string, options?: Record<string, unknown>) =>
    t(`projects.parameters.${key}`, options ?? {})
  if (!term) return <Text c="dimmed">{label('noTerm')}</Text>
  const failed = [axes, objectives].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (axes.isLoading || objectives.isLoading) return <Loader aria-label={t('app.loading')} />

  return (
    <EditableList
      items={axes.data ?? []}
      addLabel={label('newAxis')}
      onAdd={(name) => run(() => send('POST', '/axes', { term_id: term.id, name }))}
      onRename={(item, name) => run(() => send('PATCH', `/axes/${item.id}`, { name }))}
      onDelete={(item) => run(() => send('DELETE', `/axes/${item.id}`))}
      renderDetail={(axis) => (
        <Box pl="lg" pb="xs">
          <EditableList
            items={(objectives.data ?? []).filter((objective) => objective.axis_id === axis.id)}
            addLabel={label('newObjectiveFor', { name: axis.name })}
            onAdd={(name) => run(() => send('POST', '/objectives', { axis_id: axis.id, name }))}
            onRename={(item, name) => run(() => send('PATCH', `/objectives/${item.id}`, { name }))}
            onDelete={(item) => run(() => send('DELETE', `/objectives/${item.id}`))}
            hideEmpty
          />
        </Box>
      )}
    />
  )
}

/** Catalogs the municipality maintains for the projects dashboard. Dashboard admins only. */
export function ParametersPage() {
  const { t } = useTranslation()
  const action = useAction()
  const terms = useTerms()
  const departments = useDepartments()
  const programs = usePrograms()
  const owners = useOwners()
  const [termId, setTermId] = useState<string | null>(null)
  const termList = terms.data ?? []
  const selected = termList.find((term) => term.id === termId) ?? latestTerm(termList)
  const label = (key: string) => t(`projects.parameters.${key}`)

  const catalogs = [terms, departments, programs, owners]
  const failed = catalogs.find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (catalogs.some((query) => query.isLoading)) return <Loader aria-label={t('app.loading')} />

  return (
    <Stack>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {termList.length > 1 && selected && (
        <NativeSelect
          aria-label={t('projects.term.change')}
          maw={320}
          value={selected.id}
          onChange={(event) => setTermId(event.currentTarget.value)}
          data={termList.map((term) => ({ value: term.id, label: term.name }))}
        />
      )}
      <Tabs defaultValue="terms" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="terms">{label('terms')}</Tabs.Tab>
          <Tabs.Tab value="axes">{label('axes')}</Tabs.Tab>
          <Tabs.Tab value="departments">{label('departments')}</Tabs.Tab>
          <Tabs.Tab value="programs">{label('programs')}</Tabs.Tab>
          <Tabs.Tab value="owners">{label('owners')}</Tabs.Tab>
          <Tabs.Tab value="targets">{label('targets')}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="terms">
          <TermsTab terms={termList} selected={selected} run={action.run} />
        </Tabs.Panel>
        <Tabs.Panel value="axes">
          <AxesTab term={selected} run={action.run} />
        </Tabs.Panel>
        <Tabs.Panel value="departments">
          <Catalog path="/departments" field="name" items={departments.data ?? []} run={action.run} />
        </Tabs.Panel>
        <Tabs.Panel value="programs">
          <Catalog path="/programs" field="name" items={programs.data ?? []} run={action.run} />
        </Tabs.Panel>
        <Tabs.Panel value="owners">
          <Catalog
            path="/owners"
            field="full_name"
            items={(owners.data ?? []).map((owner) => ({ id: owner.id, name: owner.full_name }))}
            run={action.run}
          />
        </Tabs.Panel>
        <Tabs.Panel value="targets">
          <IndicatorTargets dashboardKey="projects" />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}
