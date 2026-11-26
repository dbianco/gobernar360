import {
  Alert,
  Button,
  Checkbox,
  Group,
  NativeSelect,
  SimpleGrid,
  Stack,
  Textarea,
  TextInput,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import { AUDIENCES, CHANNELS, CIDI_LEVELS, type Named, type Procedure } from './types'

const WHOLE_NUMBER = '[0-9]*'
const AMOUNT = '[0-9]+([.,][0-9]{1,2})?'

const numberOrNull = (text: string) => (text.trim() ? Number(text.replace(',', '.')) : null)
const textOf = (value: number | string | null | undefined) =>
  value === null || value === undefined ? '' : String(Number(value))

/** Create a procedure, or edit an existing one. */
export function ProcedureForm(props: { areas: Named[]; procedure?: Procedure; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.procedure
  const [name, setName] = useState(editing?.name ?? '')
  const [description, setDescription] = useState(editing?.description ?? '')
  const [areaId, setAreaId] = useState(editing?.area.id ?? props.areas[0]?.id ?? '')
  const [audience, setAudience] = useState(editing?.audience ?? 'both')
  const [channel, setChannel] = useState<string>(editing?.channel ?? 'in_person')
  const [url, setUrl] = useState(editing?.url ?? '')
  const [cidiLevel, setCidiLevel] = useState(textOf(editing?.cidi_level))
  const [isFree, setIsFree] = useState(editing?.is_free ?? true)
  const [cost, setCost] = useState(textOf(editing?.cost))
  const [days, setDays] = useState(textOf(editing?.duration_days))
  const [volume, setVolume] = useState(textOf(editing?.annual_volume))
  const [isActive, setIsActive] = useState(editing?.is_active ?? true)
  const label = (key: string) => t(`procedures.form.${key}`)
  const hasOnlineChannel = channel !== 'in_person'
  // Nobody signs in to what is only done in person.
  const cidiError = !hasOnlineChannel && cidiLevel !== ''

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = {
      name,
      description,
      area_id: areaId,
      audience,
      channel,
      // A link only makes sense for something that can be done online.
      url: hasOnlineChannel ? url.trim() : '',
      cidi_level: numberOrNull(cidiLevel),
      is_free: isFree,
      cost: isFree ? null : numberOrNull(cost),
      duration_days: numberOrNull(days),
      annual_volume: numberOrNull(volume),
      is_active: isActive,
    }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/procedures/${editing.id}`, body) : send('POST', '/procedures', body),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <TextInput
          label={label('name')}
          required
          withAsterisk={false}
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
        />
        <Textarea
          label={label('description')}
          rows={2}
          maxLength={5000}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NativeSelect
            label={label('area')}
            value={areaId}
            onChange={(event) => setAreaId(event.currentTarget.value)}
            data={props.areas.map((area) => ({ value: area.id, label: area.name }))}
          />
          <NativeSelect
            label={label('audience')}
            value={audience}
            onChange={(event) => setAudience(event.currentTarget.value)}
            data={AUDIENCES.map((value) => ({ value, label: t(`procedures.audiences.${value}`) }))}
          />
          <NativeSelect
            label={label('channel')}
            value={channel}
            onChange={(event) => setChannel(event.currentTarget.value)}
            data={CHANNELS.map((value) => ({ value, label: t(`procedures.channels.${value}`) }))}
          />
          <NativeSelect
            label={label('cidi')}
            description={label('cidiHint')}
            value={cidiLevel}
            onChange={(event) => setCidiLevel(event.currentTarget.value)}
            error={cidiError && t('errors.cidi_level_in_person')}
            data={[
              { value: '', label: t('procedures.cidiOptions.none') },
              ...CIDI_LEVELS.map((level) => ({
                value: String(level),
                label: t(`procedures.cidiOptions.${level}`),
              })),
            ]}
          />
        </SimpleGrid>
        {hasOnlineChannel && (
          <TextInput
            label={label('url')}
            description={label('urlHint')}
            type="url"
            pattern="https?://.+"
            maxLength={500}
            value={url}
            onChange={(event) => setUrl(event.currentTarget.value)}
          />
        )}
        <Checkbox
          label={label('isFree')}
          checked={isFree}
          onChange={(event) => setIsFree(event.currentTarget.checked)}
        />
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          {!isFree && (
            <TextInput
              label={label('cost')}
              inputMode="decimal"
              pattern={AMOUNT}
              maxLength={13}
              value={cost}
              onChange={(event) => setCost(event.currentTarget.value)}
            />
          )}
          <TextInput
            label={label('days')}
            inputMode="numeric"
            pattern={WHOLE_NUMBER}
            maxLength={4}
            value={days}
            onChange={(event) => setDays(event.currentTarget.value)}
          />
          <TextInput
            label={label('volume')}
            inputMode="numeric"
            pattern={WHOLE_NUMBER}
            maxLength={9}
            value={volume}
            onChange={(event) => setVolume(event.currentTarget.value)}
          />
        </SimpleGrid>
        <Checkbox
          label={label('isActive')}
          checked={isActive}
          onChange={(event) => setIsActive(event.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending} disabled={cidiError}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
