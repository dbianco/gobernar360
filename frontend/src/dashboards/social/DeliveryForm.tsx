import { Alert, Button, Group, NativeSelect, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { todayIso } from '../../platform/format'
import { send, useAction, useBenefits } from './api'
import { PersonPicker } from './PersonSearch'
import type { Delivery, PersonRef } from './types'

/**
 * Record a benefit handed to a person, or correct the date, quantity and note of
 * an existing record. Without `personId` the form asks who received it.
 */
export function DeliveryForm(props: { personId?: string; delivery?: Delivery; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const benefits = useBenefits()
  const editing = props.delivery
  const [person, setPerson] = useState<PersonRef | null>(null)
  const [benefitId, setBenefitId] = useState('')
  const [date, setDate] = useState(() => editing?.date ?? todayIso())
  const [quantity, setQuantity] = useState(String(editing?.quantity ?? 1))
  const [note, setNote] = useState(editing?.note ?? '')
  const label = (key: string) => t(`social.deliveries.${key}`)
  const personId = props.personId ?? person?.id
  const offered = [...(benefits.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, 'es'))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const changes = { date, quantity: Number(quantity), note }
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `/deliveries/${editing.id}`, changes)
        : send('POST', '/deliveries', { benefit_id: benefitId, person_id: personId, ...changes }),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {benefits.isError && <Alert color="red">{errorMessage(benefits.error)}</Alert>}
        {!editing && !props.personId && <PersonPicker value={person} onChange={setPerson} />}
        {!editing && benefits.data && offered.length === 0 && (
          <Text c="dimmed">{label('noBenefits')}</Text>
        )}
        {editing ? (
          <TextInput
            label={label('benefit')}
            description={label('fixed')}
            disabled
            value={editing.benefit.name}
            readOnly
          />
        ) : (
          <NativeSelect
            label={label('benefit')}
            required
            withAsterisk={false}
            value={benefitId}
            onChange={(event) => setBenefitId(event.currentTarget.value)}
            data={[
              { value: '', label: label('chooseBenefit') },
              ...offered.map((benefit) => ({
                value: benefit.id,
                label: `${benefit.name} (${benefit.category.name})`,
              })),
            ]}
          />
        )}
        <Group grow align="flex-start">
          <TextInput
            label={label('date')}
            type="date"
            required
            withAsterisk={false}
            value={date}
            onChange={(event) => setDate(event.currentTarget.value)}
          />
          <TextInput
            label={label('quantity')}
            type="number"
            min={1}
            max={1000000}
            step={1}
            required
            withAsterisk={false}
            value={quantity}
            onChange={(event) => setQuantity(event.currentTarget.value)}
          />
        </Group>
        <Textarea
          label={label('note')}
          rows={2}
          value={note}
          onChange={(event) => setNote(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button
            type="submit"
            loading={action.pending}
            disabled={!editing && (offered.length === 0 || !personId)}
          >
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
