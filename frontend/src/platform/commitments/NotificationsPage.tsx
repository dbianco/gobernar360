import { Alert, Anchor, Badge, Button, Group, Loader, Stack, Table, Text, Title } from '@mantine/core'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import { errorMessage } from '../errorMessage'
import { formatDate } from '../format'
import { HelpTh } from '../HelpTh'
import { Pager } from '../Pager'
import { useLocalTable } from '../paging'
import { SearchInput } from '../SearchInput'
import { markRead, PATH, useCommitmentAction, useNotifications } from './api'
import { newsText } from './news'
import { StateBadge } from './StateBadge'
import type { NotificationRow } from './types'

function Section(props: {
  id: 'mine' | 'others'
  rows: NotificationRow[]
  pending: boolean
  onRead: (row: NotificationRow) => void
}) {
  const { t } = useTranslation()
  const label = (key: string, options = {}) => t(`notices.${key}`, options)
  const help = (key: string) => t(`commitments.help.${key}`)
  const title = label(`sections.${props.id}`)
  const others = props.id === 'others'
  const table = useLocalTable(
    `notices.${props.id}`,
    props.rows,
    (row) => `${row.description} ${row.owner.full_name}`,
  )

  return (
    <Stack
      gap="xs"
      component="section"
      aria-label={title}
      id={props.id}
      // Clear of the fixed header when the page scrolls to it.
      style={{ scrollMarginTop: 72 }}
    >
      <Title order={3}>{title}</Title>
      <Text size="sm" c="dimmed">
        {label(`hints.${props.id}`)}
      </Text>
      {table.hasItems ? (
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={label('searchHint')}
        />
      ) : (
        <Text>{label(`empty.${props.id}`)}</Text>
      )}
      {table.hasItems && table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
      {table.rows.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover aria-label={title}>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('description')}>{t('commitments.list.description')}</HelpTh>
                {others && <HelpTh help={help('owner')}>{t('commitments.list.owner')}</HelpTh>}
                <HelpTh help={help('state')}>{t('commitments.list.state')}</HelpTh>
                <HelpTh help={help('dueDate')}>{t('commitments.list.dueDate')}</HelpTh>
                <HelpTh help={label('help.news')}>{label('news')}</HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((row) => (
                <Table.Tr key={row.id}>
                  <Table.Td>
                    <Anchor
                      component={Link}
                      to={`${PATH}/${row.id}`}
                      fw={row.news.length > 0 ? 700 : undefined}
                    >
                      {row.description}
                    </Anchor>
                  </Table.Td>
                  {others && <Table.Td>{row.owner.full_name}</Table.Td>}
                  <Table.Td>
                    <StateBadge state={row.state} />
                  </Table.Td>
                  <Table.Td>{formatDate(row.due_date)}</Table.Td>
                  <Table.Td>
                    {row.news.length > 0 && (
                      <Group gap="xs">
                        {row.news.map((news) => (
                          <Badge key={news.kind} variant="light" tt="none">
                            {newsText(t, news)}
                          </Badge>
                        ))}
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          disabled={props.pending}
                          aria-label={label('readNamed', { name: row.description })}
                          onClick={() => props.onRead(row)}
                        >
                          {label('read')}
                        </Button>
                      </Group>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Pager {...table.pager} />
    </Stack>
  )
}

/** What one owes and follows, and what changed about it since last looked at. */
export function NotificationsPage() {
  const { t } = useTranslation()
  const { hash } = useLocation()
  const notifications = useNotifications()
  const action = useCommitmentAction()
  const data = notifications.data
  const loaded = data !== undefined
  const hasNews = [...(data?.mine ?? []), ...(data?.others ?? [])].some((row) => row.news.length > 0)
  const read = (row?: NotificationRow) => void action.run(() => markRead(row?.id))

  // Each icon of the header leads to its own list.
  useEffect(() => {
    if (!loaded) return
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [loaded, hash])

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>{t('notices.title')}</Title>
        {hasNews && (
          <Button variant="default" loading={action.pending} onClick={() => read()}>
            {t('notices.readAll')}
          </Button>
        )}
      </Group>
      {notifications.isLoading && <Loader aria-label={t('app.loading')} />}
      {notifications.isError && <Alert color="red">{errorMessage(notifications.error)}</Alert>}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {data && (
        <>
          <Section id="mine" rows={data.mine} pending={action.pending} onRead={read} />
          <Section id="others" rows={data.others} pending={action.pending} onRead={read} />
        </>
      )}
    </Stack>
  )
}
