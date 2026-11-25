import { MultiSelect, Stack, Textarea } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import type { Member, UserRef } from './types'

export interface MeetingValues {
  date: string
  attendee_ids: string[]
  guests: string
}

/** Date and people of a meeting, the same when preparing it and when correcting it. */
export function MeetingFields(props: {
  values: MeetingValues
  onChange: (values: MeetingValues) => void
  members: Member[]
  /** Already in the list; some may have left the municipality. */
  attendees?: UserRef[]
  /** No meeting may be dated before it. */
  minDate?: string | null
}) {
  const { t } = useTranslation()
  const { values, members } = props
  const set = (changes: Partial<MeetingValues>) => props.onChange({ ...values, ...changes })
  const former = (props.attendees ?? []).filter(
    (attendee) => !members.some((member) => member.id === attendee.id),
  )

  return (
    <Stack>
      <DateField
        label={t('cabinet.meeting.date')}
        required
        maw={220}
        min={props.minDate}
        value={values.date}
        onChange={(date) => set({ date })}
      />
      <MultiSelect
        label={t('cabinet.meeting.attendees')}
        searchable
        nothingFoundMessage={t('app.noMatches')}
        value={values.attendee_ids}
        onChange={(attendee_ids) => set({ attendee_ids })}
        data={[...members, ...former].map((member) => ({
          value: member.id,
          label: member.full_name,
        }))}
      />
      <Textarea
        label={t('cabinet.meeting.guests')}
        description={t('cabinet.meeting.guestsHint')}
        rows={2}
        maxLength={10000}
        value={values.guests}
        onChange={(event) => set({ guests: event.currentTarget.value })}
      />
    </Stack>
  )
}
