import { Text, Timeline as MantineTimeline } from '@mantine/core'
import {
  IconArrowRight,
  IconCategory,
  IconInbox,
  IconMessage,
  IconSwitchHorizontal,
} from '@tabler/icons-react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { formatDateTime } from './format'
import type { TimelineEvent } from './types'

const ICONS = {
  created: IconInbox,
  transition: IconArrowRight,
  reassigned: IconSwitchHorizontal,
  retyped: IconCategory,
  comment: IconMessage,
}

function title(event: TimelineEvent, t: TFunction): string {
  const state = (value: string | null) => (value ? t(`complaints.states.${value}`) : '')
  const key = `complaints.timeline.${event.kind}`
  switch (event.kind) {
    case 'created':
      return t(key, { area: event.to_area?.name ?? '' })
    case 'transition':
      return t(key, { from: state(event.from_state), to: state(event.to_state) })
    case 'reassigned':
      return t(key, { from: event.from_area?.name ?? '', to: event.to_area?.name ?? '' })
    case 'retyped':
      return t(key, { from: event.from_type?.name ?? '', to: event.to_type?.name ?? '' })
    default:
      return t(key)
  }
}

/** Everything that happened to a complaint, oldest first: what, who, when and why. */
export function Timeline({ events }: { events: TimelineEvent[] }) {
  const { t } = useTranslation()
  return (
    <MantineTimeline active={events.length - 1} bulletSize={24} lineWidth={2}>
      {events.map((event) => {
        const Icon = ICONS[event.kind]
        return (
          <MantineTimeline.Item
            key={event.id}
            bullet={<Icon size={14} aria-hidden />}
            title={title(event, t)}
          >
            {event.note && <Text size="sm">{event.note}</Text>}
            <Text size="xs" c="dimmed" mt={4}>
              {t('complaints.timeline.byAt', {
                user: event.user?.full_name ?? t('complaints.timeline.unknownUser'),
                at: formatDateTime(event.at),
              })}
            </Text>
          </MantineTimeline.Item>
        )
      })}
    </MantineTimeline>
  )
}
