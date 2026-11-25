import { ActionIcon, Anchor, Group, HoverCard, Indicator, Stack, Text } from '@mantine/core'
import { IconBell, IconChecklist, type Icon } from '@tabler/icons-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { formatDate } from '../format'
import { NOTIFICATIONS_PATH, PATH, useNotifications } from './api'
import { newsText } from './news'
import { StateBadge } from './StateBadge'
import type { NotificationRow } from './types'

const SHOWN = 5

/** An icon with a count that shows a preview on hover and opens its list on click. */
function HeaderIcon(props: {
  icon: Icon
  to: string
  /** Says the count too: it is what a screen reader gets of it. */
  label: string
  title: string
  count: number
  color: string
  children: ReactNode
}) {
  const { t } = useTranslation()
  return (
    <HoverCard width={360} position="bottom-end" shadow="md" openDelay={150} withinPortal>
      <HoverCard.Target>
        <Indicator
          label={props.count > 99 ? '99+' : props.count}
          disabled={props.count === 0}
          color={props.color}
          size={16}
          offset={4}
        >
          <ActionIcon
            component={Link}
            to={props.to}
            variant="subtle"
            color="gray"
            size="lg"
            aria-label={props.label}
          >
            <props.icon size={20} stroke={1.5} aria-hidden />
          </ActionIcon>
        </Indicator>
      </HoverCard.Target>
      <HoverCard.Dropdown>
        <Stack gap="xs">
          <Text fw={600} size="sm">
            {props.title}
          </Text>
          {props.children}
          <Anchor component={Link} to={props.to} size="sm">
            {t('notices.seeAll')}
          </Anchor>
        </Stack>
      </HoverCard.Dropdown>
    </HoverCard>
  )
}

function Preview(props: { rows: NotificationRow[]; line: (row: NotificationRow) => ReactNode }) {
  const { t } = useTranslation()
  const more = props.rows.length - SHOWN
  return (
    <>
      {props.rows.slice(0, SHOWN).map((row) => (
        <Stack key={row.id} gap={0}>
          <Anchor component={Link} to={`${PATH}/${row.id}`} size="sm" lineClamp={1}>
            {row.description}
          </Anchor>
          {props.line(row)}
        </Stack>
      ))}
      {more > 0 && (
        <Text size="xs" c="dimmed">
          {t('notices.more', { count: more })}
        </Text>
      )}
    </>
  )
}

/** Beside the user's name: what they owe, and what changed in what they follow. */
export function HeaderNotices() {
  const { t } = useTranslation()
  const { data } = useNotifications()
  const mine = data?.mine ?? []
  const overdue = mine.filter((row) => row.state === 'overdue').length
  const news = [...mine, ...(data?.others ?? [])].filter((row) => row.news.length > 0)
  const label = (key: string, options = {}) => t(`notices.${key}`, options)

  return (
    <Group gap={4} wrap="nowrap">
      <HeaderIcon
        icon={IconChecklist}
        to={NOTIFICATIONS_PATH}
        title={label('sections.mine')}
        label={
          overdue > 0
            ? label('mineOverdueLabel', { count: mine.length, overdue })
            : label('mineLabel', { count: mine.length })
        }
        count={mine.length}
        color={overdue > 0 ? 'red' : 'blue'}
      >
        {mine.length === 0 && <Text size="sm">{label('empty.mine')}</Text>}
        <Preview
          rows={mine}
          line={(row) => (
            <Group gap="xs">
              <StateBadge state={row.state} />
              <Text size="xs" c="dimmed">
                {formatDate(row.due_date)}
              </Text>
            </Group>
          )}
        />
      </HeaderIcon>
      <HeaderIcon
        icon={IconBell}
        to={`${NOTIFICATIONS_PATH}#others`}
        title={label('title')}
        label={label('newsLabel', { count: news.length })}
        count={news.length}
        color="red"
      >
        {news.length === 0 && <Text size="sm">{label('noNews')}</Text>}
        <Preview
          rows={news}
          line={(row) => (
            <Text size="xs" c="dimmed">
              {row.news.map((one) => newsText(t, one)).join(' · ')}
            </Text>
          )}
        />
      </HeaderIcon>
    </Group>
  )
}
