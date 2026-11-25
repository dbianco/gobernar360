import { Anchor, Group, Text, VisuallyHidden } from '@mantine/core'
import { IconLink, IconLock } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { StatusLight } from '../status/StatusLight'
import type { Subject } from './types'

/**
 * What something is linked to. Whoever may see it gets its name and the way there; anyone
 * else reads that there is a link to something of that kind, and nothing else.
 */
export function SubjectLabel({
  subject,
  stateOnly = false,
}: {
  subject: Subject
  /** Next to a title that already names it: only the month's state is shown. */
  stateOnly?: boolean
}) {
  const { t } = useTranslation()

  if (subject.access !== 'visible' || !subject.path) {
    if (stateOnly) return null
    const specific = `subjects.${subject.access}.${subject.dashboard_key}.${subject.kind}`
    const general = `subjects.${subject.access}.${subject.kind === 'month' ? 'month' : 'record'}`
    const Mark = subject.access === 'restricted' ? IconLock : IconLink
    return (
      <Group gap={4} wrap="nowrap" c="dimmed">
        <Mark size={14} aria-hidden style={{ flexShrink: 0 }} />
        <Text size="sm" fs="italic">
          {t([specific, general])}
        </Text>
      </Group>
    )
  }
  if (stateOnly) {
    return (
      <Group gap={4} wrap="nowrap">
        <StatusLight color={subject.color} size={16} />
        <Anchor component={Link} to={subject.path} size="sm">
          {t(`status.states.${subject.color ?? 'none'}`)}
        </Anchor>
      </Group>
    )
  }
  return (
    <Group gap={4} wrap="nowrap">
      {subject.color ? (
        <StatusLight color={subject.color} size={16} />
      ) : (
        <IconLink size={14} aria-hidden style={{ flexShrink: 0 }} />
      )}
      <Anchor component={Link} to={subject.path} size="sm">
        {subject.label}
        {subject.color && ' '}
        {subject.color && (
          <VisuallyHidden>{`(${t(`status.states.${subject.color}`)})`}</VisuallyHidden>
        )}
      </Anchor>
    </Group>
  )
}
