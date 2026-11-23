import {
  Alert,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber, formatPercent } from '../../platform/format'
import { hasLevel } from '../../platform/types'
import { send, useAction, useAxes, useIndicators, useObjectives } from './api'
import { useTerm } from './termContext'
import type { Indicator } from './types'
import { Pager } from '../../platform/Pager'
import { useLocalTable } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

const numberOrNull = (text: string) => (text.trim() === '' ? null : text.trim())
const textOf = (value: number | null | undefined) => (value == null ? '' : String(value))

function IndicatorForm(props: { indicator?: Indicator; onDone: () => void }) {
  const { t } = useTranslation()
  const { term } = useTerm()
  const axes = useAxes(term.id)
  const objectives = useObjectives(term.id)
  const action = useAction()
  const [objectiveId, setObjectiveId] = useState(props.indicator?.objective.id ?? '')
  const [name, setName] = useState(props.indicator?.name ?? '')
  const [unit, setUnit] = useState(props.indicator?.unit ?? '')
  const [baseline, setBaseline] = useState(textOf(props.indicator?.baseline))
  const [target, setTarget] = useState(textOf(props.indicator?.target))
  const [current, setCurrent] = useState(textOf(props.indicator?.current_value))
  const label = (key: string) => t(`projects.indicators.${key}`)
  const axisName = (axisId: string) => axes.data?.find((axis) => axis.id === axisId)?.name ?? ''

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = {
      objective_id: objectiveId,
      name,
      unit,
      baseline: numberOrNull(baseline),
      target: numberOrNull(target),
      current_value: numberOrNull(current),
    }
    const saved = await action.run(() =>
      props.indicator
        ? send('PATCH', `/indicators/${props.indicator.id}`, body)
        : send('POST', '/indicators', body),
    )
    if (saved) props.onDone()
  }

  const numeric = (text: string, value: string, onChange: (value: string) => void) => (
    <TextInput
      label={text}
      type="number"
      step="any"
      value={value}
      onChange={(event) => onChange(event.currentTarget.value)}
    />
  )

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <NativeSelect
          label={label('objective')}
          required
          value={objectiveId}
          onChange={(event) => setObjectiveId(event.currentTarget.value)}
          data={[
            { value: '', label: t('projects.form.choose') },
            ...(objectives.data ?? []).map((objective) => ({
              value: objective.id,
              label: `${axisName(objective.axis_id)} › ${objective.name}`,
            })),
          ]}
        />
        <TextInput
          label={label('name')}
          required
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={label('unit')}
            maxLength={50}
            value={unit}
            onChange={(event) => setUnit(event.currentTarget.value)}
          />
          {numeric(label('baseline'), baseline, setBaseline)}
          {numeric(label('target'), target, setTarget)}
          {numeric(label('currentValue'), current, setCurrent)}
        </SimpleGrid>
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
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

/** Strategic indicators of the term, each with its current value against its target. */
export function IndicatorsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { term } = useTerm()
  const indicators = useIndicators(term.id)
  const table = useLocalTable('projects.indicators', indicators.data, (indicator) => indicator.name)
  const objectives = useObjectives(term.id)
  const action = useAction()
  const [editing, setEditing] = useState<Indicator | 'new' | null>(null)
  const canEdit = hasLevel(me, 'projects', 'editor')
  const label = (key: string) => t(`projects.indicators.${key}`)
  const hasObjectives = (objectives.data?.length ?? 0) > 0

  const valueText = (indicator: Indicator) => {
    const current = formatNumber(indicator.current_value, 2)
    const text = indicator.target === null ? current : `${current} / ${formatNumber(indicator.target, 2)}`
    return indicator.unit ? `${text} ${indicator.unit}` : text
  }
  const achievement = (indicator: Indicator) =>
    indicator.target && indicator.current_value !== null
      ? formatPercent(Math.round((indicator.current_value / indicator.target) * 100))
      : t('app.none')

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={4}>{label('title')}</Title>
        {canEdit && hasObjectives && (
          <Button onClick={() => setEditing('new')}>{label('add')}</Button>
        )}
      </Group>
      {canEdit && objectives.data && !hasObjectives && (
        <Text c="dimmed">{label('needsObjectives')}</Text>
      )}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {indicators.isLoading && <Loader aria-label={t('app.loading')} />}
      {indicators.isError && <Alert color="red">{errorMessage(indicators.error)}</Alert>}
      {indicators.data?.length === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {table.hasItems && (
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={label('searchHint')}
        />
      )}
      {table.hasItems && table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
      {table.rows.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={t('projects.help.indicatorsPage.name')}>{label('name')}</HelpTh>
                <HelpTh help={t('projects.help.indicatorsPage.axis')}>
                  {t('projects.filters.axis')}
                </HelpTh>
                <HelpTh help={t('projects.help.indicatorsPage.objective')}>
                  {label('objective')}
                </HelpTh>
                <HelpTh help={t('projects.help.indicatorsPage.currentValue')}>
                  {label('currentValue')}
                </HelpTh>
                <HelpTh help={t('projects.help.indicatorsPage.achievement')}>
                  {label('achievement')}
                </HelpTh>
                {canEdit && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((indicator) => (
                <Table.Tr key={indicator.id}>
                  <Table.Td>{indicator.name}</Table.Td>
                  <Table.Td>{indicator.axis.name}</Table.Td>
                  <Table.Td>{indicator.objective.name}</Table.Td>
                  <Table.Td>{valueText(indicator)}</Table.Td>
                  <Table.Td>{achievement(indicator)}</Table.Td>
                  {canEdit && (
                    <Table.Td>
                      <Group gap="xs" justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="default"
                          aria-label={t('projects.indicators.editNamed', { name: indicator.name })}
                          onClick={() => setEditing(indicator)}
                        >
                          {t('app.edit')}
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          aria-label={t('projects.indicators.deleteNamed', {
                            name: indicator.name,
                          })}
                          onClick={() =>
                            void action.run(() => send('DELETE', `/indicators/${indicator.id}`))
                          }
                        >
                          {t('app.delete')}
                        </Button>
                      </Group>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Pager {...table.pager} />
      <Modal opened={editing !== null} onClose={() => setEditing(null)} title={label('title')}>
        {editing !== null && (
          <IndicatorForm
            indicator={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
