import { Alert, Button, Group, NativeSelect, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import { moveLabelKey } from './moves'
import {
  type ComplaintDetail,
  type ComplaintType,
  type Named,
  NOTE_REQUIRED,
  type State,
} from './types'

function ActionForm(props: {
  path: string
  body: () => Record<string, unknown>
  onDone: () => void
  submitLabel: string
  children: ReactNode
}) {
  const { t } = useTranslation()
  const action = useAction()

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() => send('POST', props.path, props.body()))
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {props.children}
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending}>
            {props.submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

function NoteField(props: { required: boolean; value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation()
  return (
    <Textarea
      label={t('complaints.actions.note')}
      description={t(`complaints.actions.${props.required ? 'noteRequired' : 'noteOptional'}`)}
      required={props.required}
      withAsterisk={false}
      rows={3}
      maxLength={2000}
      value={props.value}
      onChange={(event) => props.onChange(event.currentTarget.value)}
    />
  )
}

/** Move the complaint to the next state, with a note. */
export function MoveForm(props: { complaint: ComplaintDetail; to: State; onDone: () => void }) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  const { complaint, to } = props
  return (
    <ActionForm
      path={`/complaints/${complaint.id}/transitions`}
      body={() => ({ to_state: to, note })}
      onDone={props.onDone}
      submitLabel={t(`complaints.moves.${moveLabelKey(complaint.state, to)}`)}
    >
      <Text>
        {t('complaints.actions.moveFromTo', {
          from: t(`complaints.states.${complaint.state}`),
          to: t(`complaints.states.${to}`),
        })}
      </Text>
      {to === 'waiting' && <Text size="sm">{t('complaints.actions.waitingHint')}</Text>}
      <NoteField required={NOTE_REQUIRED.includes(to)} value={note} onChange={setNote} />
    </ActionForm>
  )
}

/** Send the complaint to another area's queue. */
export function ReassignForm(props: {
  complaint: ComplaintDetail
  areas: Named[]
  onDone: () => void
}) {
  const { t } = useTranslation()
  const others = props.areas.filter((area) => area.id !== props.complaint.area.id)
  const [areaId, setAreaId] = useState(others[0]?.id ?? '')
  const [note, setNote] = useState('')
  return (
    <ActionForm
      path={`/complaints/${props.complaint.id}/assignment`}
      body={() => ({ area_id: areaId, note })}
      onDone={props.onDone}
      submitLabel={t('complaints.actions.reassign')}
    >
      <NativeSelect
        label={t('complaints.actions.newArea')}
        value={areaId}
        onChange={(event) => setAreaId(event.currentTarget.value)}
        data={others.map((area) => ({ value: area.id, label: area.name }))}
      />
      <NoteField required={false} value={note} onChange={setNote} />
    </ActionForm>
  )
}

/** A note on the timeline that changes nothing else. */
export function CommentForm(props: { complaint: ComplaintDetail; onDone: () => void }) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  return (
    <ActionForm
      path={`/complaints/${props.complaint.id}/comments`}
      body={() => ({ note })}
      onDone={props.onDone}
      submitLabel={t('complaints.actions.comment')}
    >
      <NoteField required value={note} onChange={setNote} />
    </ActionForm>
  )
}

/** Correct what was registered: type, zone, address or description. */
export function EditForm(props: {
  complaint: ComplaintDetail
  types: ComplaintType[]
  zones: Named[]
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const { complaint } = props
  const offered = props.types.filter((type) => type.is_active || type.id === complaint.type.id)
  const [typeId, setTypeId] = useState(complaint.type.id)
  const [zoneId, setZoneId] = useState(complaint.zone.id)
  const [address, setAddress] = useState(complaint.address)
  const [description, setDescription] = useState(complaint.description)
  const label = (key: string) => t(`complaints.form.${key}`)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { type_id: typeId, zone_id: zoneId, address, description }
    const saved = await action.run(() => send('PATCH', `/complaints/${complaint.id}`, body))
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <NativeSelect
          label={label('type')}
          description={t('complaints.actions.retypeHint')}
          value={typeId}
          onChange={(event) => setTypeId(event.currentTarget.value)}
          data={offered.map((type) => ({ value: type.id, label: type.name }))}
        />
        <NativeSelect
          label={label('zone')}
          value={zoneId}
          onChange={(event) => setZoneId(event.currentTarget.value)}
          data={props.zones.map((zone) => ({ value: zone.id, label: zone.name }))}
        />
        <TextInput
          label={label('address')}
          required
          withAsterisk={false}
          maxLength={200}
          value={address}
          onChange={(event) => setAddress(event.currentTarget.value)}
        />
        <Textarea
          label={label('description')}
          rows={3}
          maxLength={5000}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
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
