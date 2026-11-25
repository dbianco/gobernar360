import { Stack, Textarea } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import { type UserRef, withFormer } from '../../platform/directory'
import { PeopleSelect } from '../../platform/PersonSelect'

export interface MeetingValues {
  date: string
  attendee_ids: string[]
  guests: string
}

/** Date and people of a meeting, the same when preparing it and when correcting it. */
export function MeetingFields(props: {
  values: MeetingValues
  onChange: (values: MeetingValues) => void
  members: UserRef[] | undefined
  /** Already in the list; some may have left the municipality. */
  attendees?: UserRef[]
  /** No meeting may be dated before it. */
  minDate?: string | null
}) {
  const { t } = useTranslation()
  const { values } = props
  const set = (changes: Partial<MeetingValues>) => props.onChange({ ...values, ...changes })

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
      <PeopleSelect
        label={t('cabinet.meeting.attendees')}
        value={values.attendee_ids}
        onChange={(attendee_ids) => set({ attendee_ids })}
        people={withFormer(props.members, props.attendees ?? [])}
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
