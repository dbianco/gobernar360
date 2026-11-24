import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { formatTimestampDate } from '../format'
import { StatusLight } from '../status/StatusLight'
import {
  closeMonth,
  reopenReport,
  setReportPublished,
  usePreview,
  useReportAction,
  useReports,
} from './api'
import type { ReportSummary } from './types'

const LISTED_MONTHS = 12

type Run = ReturnType<typeof useReportAction>['run']

interface MonthRow {
  year: number
  month: number
  current: ReportSummary | null
  earlier: ReportSummary[]
}

function useMonthName() {
  const { t } = useTranslation()
  return (year: number, month: number) =>
    t('status.monthYear', { month: t(`status.months.${month}`), year })
}

/** The months that have ended, last twelve first, plus any older month with a report. */
function monthRows(reports: ReportSummary[]): MonthRow[] {
  const now = new Date()
  const last = now.getFullYear() * 12 + now.getMonth() - 1
  const indexes = new Set(Array.from({ length: LISTED_MONTHS }, (_, back) => last - back))
  for (const report of reports) indexes.add(report.year * 12 + report.month - 1)
  return [...indexes]
    .sort((a, b) => b - a)
    .map((index) => {
      const year = Math.floor(index / 12)
      const month = (index % 12) + 1
      const versions = reports.filter((r) => r.year === year && r.month === month)
      return {
        year,
        month,
        current: versions.find((r) => r.status !== 'superseded') ?? null,
        earlier: versions.filter((r) => r.status === 'superseded'),
      }
    })
}

function CloseMonthModal(props: {
  year: number
  month: number
  run: Run
  error: string | null
  onCancel: () => void
  onClosed: () => void
}) {
  const { t } = useTranslation()
  const monthName = useMonthName()
  const preview = usePreview(props.year, props.month)
  const [comments, setComments] = useState<Record<string, string> | null>(null)
  const [pending, setPending] = useState(false)
  const label = (key: string, options = {}) => t(`reports.${key}`, options)
  const written = comments ?? preview.data?.comments ?? {}

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    const closed = await props.run(() => closeMonth(props.year, props.month, written))
    setPending(false)
    if (closed) props.onClosed()
  }

  return (
    <Modal
      opened
      onClose={props.onCancel}
      size="lg"
      title={label('closeTitle', { month: monthName(props.year, props.month) })}
    >
      {preview.isLoading && <Loader aria-label={t('app.loading')} />}
      {preview.isError && <Alert color="red">{errorMessage(preview.error)}</Alert>}
      {preview.data && (
        <form onSubmit={(event) => void submit(event)}>
          <Stack>
            <Text size="sm">{label('closeIntro')}</Text>
            {props.error && <Alert color="red">{props.error}</Alert>}
            {preview.data.content.dashboards.map((dashboard) => {
              const withTarget = dashboard.indicators.filter((i) => i.on_track !== null)
              const met = withTarget.filter((i) => i.on_track).length
              return (
                <Stack key={dashboard.key} gap={6}>
                  <Group gap="xs">
                    <StatusLight color={dashboard.light} size={22} />
                    <Text fw={600}>{dashboard.name}</Text>
                    <Text size="sm" c="dimmed">
                      {t(`status.states.${dashboard.light ?? 'none'}`)} ·{' '}
                      {withTarget.length
                        ? label('indicatorsOnTrack', { met, total: withTarget.length })
                        : label('noTargets')}
                    </Text>
                  </Group>
                  <Textarea
                    label={label('comment', { dashboard: dashboard.name })}
                    description={label('commentHint')}
                    rows={3}
                    maxLength={2000}
                    value={written[dashboard.key] ?? ''}
                    onChange={(event) =>
                      setComments({ ...written, [dashboard.key]: event.currentTarget.value })
                    }
                  />
                </Stack>
              )
            })}
            <Group justify="flex-end">
              <Button variant="default" onClick={props.onCancel}>
                {t('app.cancel')}
              </Button>
              <Button type="submit" loading={pending}>
                {label('confirmClose')}
              </Button>
            </Group>
          </Stack>
        </form>
      )}
    </Modal>
  )
}

function ReopenModal(props: { report: ReportSummary; run: Run; onDone: () => void }) {
  const { t } = useTranslation()
  const monthName = useMonthName()
  const { report } = props
  const month = monthName(report.year, report.month)
  return (
    <Modal opened onClose={props.onDone} title={t('reports.reopenTitle', { month })}>
      <Stack>
        <Text size="sm">
          {t('reports.reopenBody', { version: report.version, next: report.version + 1 })}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button
            color="red"
            onClick={async () => {
              await props.run(() => reopenReport(report.id))
              props.onDone()
            }}
          >
            {t('reports.reopen')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

/**
 * The municipality's monthly reports, for its administrators: close a month with a comment
 * per dashboard, download it, reopen it, and choose which ones the public page shows.
 */
export function ReportsPage() {
  const { t } = useTranslation()
  const monthName = useMonthName()
  const reports = useReports()
  const action = useReportAction()
  const [closing, setClosing] = useState<{ year: number; month: number } | null>(null)
  const [reopening, setReopening] = useState<ReportSummary | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const label = (key: string, options = {}) => t(`reports.${key}`, options)
  const pdf = (report: ReportSummary) => downloadUrl(`/reports/${report.id}/pdf`)

  return (
    <Stack>
      <Title order={2}>{label('title')}</Title>
      <Text size="sm" c="dimmed" maw={820}>
        {label('intro')}
      </Text>
      {notice && (
        <Alert color="green" withCloseButton onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {reports.isLoading && <Loader aria-label={t('app.loading')} />}
      {reports.isError && <Alert color="red">{errorMessage(reports.error)}</Alert>}
      {reports.data && (
        <Table.ScrollContainer minWidth={760}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{label('month')}</Table.Th>
                <Table.Th>{label('state')}</Table.Th>
                <Table.Th>{label('closedAt')}</Table.Th>
                <Table.Th>{label('publishedColumn')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {monthRows(reports.data).map(({ year, month, current, earlier }) => {
                const name = monthName(year, month)
                const closed = current?.status === 'closed' ? current : null
                return (
                  <Table.Tr key={`${year}-${month}`}>
                    <Table.Th scope="row" fw={500}>
                      {name}
                    </Table.Th>
                    <Table.Td>
                      <Stack gap={2}>
                        <Text size="sm">
                          {label(`states.${current?.status ?? 'open'}`)}
                          {current && ` · ${label('version', { version: current.version })}`}
                        </Text>
                        {earlier.length > 0 && (
                          <Group gap={6}>
                            <Text size="xs" c="dimmed">
                              {label('earlier')}
                            </Text>
                            {earlier.map((old) => (
                              <Anchor key={old.id} size="xs" href={pdf(old)}>
                                {label('downloadVersion', { version: old.version })}
                              </Anchor>
                            ))}
                          </Group>
                        )}
                      </Stack>
                    </Table.Td>
                    <Table.Td>{formatTimestampDate(closed?.closed_at)}</Table.Td>
                    <Table.Td>
                      {closed && (
                        <Badge variant="light" color={closed.published ? 'teal' : 'gray'}>
                          {label(closed.published ? 'published' : 'notPublished')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs" justify="flex-end" wrap="nowrap">
                        {!closed && (
                          <Button
                            size="xs"
                            aria-label={label('closeNamed', { month: name })}
                            onClick={() => setClosing({ year, month })}
                          >
                            {label('close')}
                          </Button>
                        )}
                        {closed && (
                          <>
                            <Button
                              size="xs"
                              variant="light"
                              component="a"
                              href={pdf(closed)}
                              aria-label={label('downloadNamed', { month: name })}
                            >
                              {label('download')}
                            </Button>
                            <Button
                              size="xs"
                              variant="default"
                              aria-label={label(
                                closed.published ? 'unpublishNamed' : 'publishNamed',
                                { month: name },
                              )}
                              disabled={action.pending}
                              onClick={() =>
                                void action.run(() =>
                                  setReportPublished(closed.id, !closed.published),
                                )
                              }
                            >
                              {label(closed.published ? 'unpublish' : 'publish')}
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              color="red"
                              aria-label={label('reopenNamed', { month: name })}
                              onClick={() => setReopening(closed)}
                            >
                              {label('reopen')}
                            </Button>
                          </>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                )
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {closing && (
        <CloseMonthModal
          {...closing}
          run={action.run}
          error={action.error}
          onCancel={() => setClosing(null)}
          onClosed={() => {
            setNotice(label('closed', { month: monthName(closing.year, closing.month) }))
            setClosing(null)
          }}
        />
      )}
      {reopening && (
        <ReopenModal report={reopening} run={action.run} onDone={() => setReopening(null)} />
      )}
    </Stack>
  )
}
