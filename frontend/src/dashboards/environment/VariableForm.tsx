import { Alert, Button, Group, NativeSelect, SimpleGrid, Stack, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import { numberText, parseNumber } from './numbers'
import {
  AGGREGATIONS,
  DIRECTIONS,
  FREQUENCIES,
  SOURCES,
  type Subcategory,
  type Variable,
} from './types'

/** Create a variable in one of the given subcategories, or edit an existing one. */
export function VariableForm(props: {
  subcategories: Subcategory[]
  variable?: Variable
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.variable
  const [subcategoryId, setSubcategoryId] = useState(
    editing?.subcategory.id ?? props.subcategories[0]?.id ?? '',
  )
  const [name, setName] = useState(editing?.name ?? '')
  const [unit, setUnit] = useState(editing?.unit ?? '')
  const [frequency, setFrequency] = useState<string>(editing?.frequency ?? 'monthly')
  const [target, setTarget] = useState(numberText(editing?.target))
  const [targetInvalid, setTargetInvalid] = useState(false)
  const [direction, setDirection] = useState<string>(editing?.direction ?? 'higher_is_better')
  const [source, setSource] = useState<string>(editing?.source ?? 'municipal')
  const [aggregation, setAggregation] = useState<string>(editing?.annual_aggregation ?? 'sum')
  const label = (key: string) => t(`environment.parameters.${key}`)
  const options = (group: string, values: readonly string[]) =>
    values.map((value) => ({ value, label: t(`environment.${group}.${value}`) }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const parsedTarget = parseNumber(target)
    setTargetInvalid(parsedTarget === undefined)
    if (parsedTarget === undefined) return
    const body = {
      subcategory_id: subcategoryId,
      name,
      unit,
      target: parsedTarget,
      direction,
      source,
      annual_aggregation: aggregation,
    }
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `/variables/${editing.id}`, body)
        : send('POST', '/variables', { ...body, frequency }),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <NativeSelect
          label={label('subcategory')}
          value={subcategoryId}
          onChange={(event) => setSubcategoryId(event.currentTarget.value)}
          data={props.subcategories.map((item) => ({ value: item.id, label: item.name }))}
        />
        <TextInput
          label={label('name')}
          required
          withAsterisk={false}
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
          <NativeSelect
            label={label('frequency')}
            description={editing ? label('frequencyFixed') : undefined}
            disabled={Boolean(editing)}
            value={frequency}
            onChange={(event) => setFrequency(event.currentTarget.value)}
            data={options('frequencies', FREQUENCIES)}
          />
          <TextInput
            label={label('target')}
            description={label('targetHint')}
            inputMode="decimal"
            error={targetInvalid ? t('environment.invalidNumber') : undefined}
            value={target}
            onChange={(event) => setTarget(event.currentTarget.value)}
          />
          <NativeSelect
            label={label('direction')}
            value={direction}
            onChange={(event) => setDirection(event.currentTarget.value)}
            data={options('directions', DIRECTIONS)}
          />
          <NativeSelect
            label={label('source')}
            value={source}
            onChange={(event) => setSource(event.currentTarget.value)}
            data={options('sources', SOURCES)}
          />
          {frequency === 'monthly' && (
            <NativeSelect
              label={label('aggregation')}
              value={aggregation}
              onChange={(event) => setAggregation(event.currentTarget.value)}
              data={options('aggregations', AGGREGATIONS)}
            />
          )}
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
