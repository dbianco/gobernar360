import { Alert, Button, Loader, Stack, Table, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { errorMessage } from '../../platform/errorMessage'
import { HelpTh } from '../../platform/HelpTh'
import { useQueue, useQueues } from './api'
import { ComplaintsTable } from './ComplaintsTable'

/** Each area's open complaints, closest to their deadline first. */
export function QueuesPage() {
  const { t } = useTranslation()
  const queues = useQueues()
  const [params, setParams] = useSearchParams()
  const label = (key: string, options = {}) => t(`complaints.queues.${key}`, options)
  const help = (key: string) => t(`complaints.help.queues.${key}`)
  const areaId = params.get('area') ?? queues.data?.[0]?.area.id ?? ''
  const queue = useQueue(areaId)
  const chosen = queues.data?.find((item) => item.area.id === areaId)

  if (queues.isError) return <Alert color="red">{errorMessage(queues.error)}</Alert>
  if (!queues.data) return <Loader aria-label={t('app.loading')} />
  if (queues.data.length === 0) return <Text c="dimmed">{label('noAreas')}</Text>

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {label('intro')}
      </Text>
      <Table.ScrollContainer minWidth={560}>
        <Table aria-label={label('areasLabel')}>
          <Table.Thead>
            <Table.Tr>
              <HelpTh help={help('area')}>{label('area')}</HelpTh>
              <HelpTh help={help('open')} ta="right">
                {label('open')}
              </HelpTh>
              <HelpTh help={help('atRisk')} ta="right">
                {label('atRisk')}
              </HelpTh>
              <HelpTh help={help('overdue')} ta="right">
                {label('overdue')}
              </HelpTh>
              <HelpTh help={help('paused')} ta="right">
                {label('paused')}
              </HelpTh>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {queues.data.map((item) => (
              <Table.Tr
                key={item.area.id}
                bg={item.area.id === areaId ? 'var(--mantine-color-default-hover)' : undefined}
              >
                <Table.Td fw={item.area.id === areaId ? 700 : undefined}>{item.area.name}</Table.Td>
                <Table.Td ta="right">{item.open}</Table.Td>
                <Table.Td ta="right">{item.at_risk}</Table.Td>
                <Table.Td ta="right">{item.overdue}</Table.Td>
                <Table.Td ta="right">{item.paused}</Table.Td>
                <Table.Td ta="right">
                  <Button
                    size="compact-xs"
                    variant={item.area.id === areaId ? 'light' : 'default'}
                    aria-label={label('showNamed', { name: item.area.name })}
                    aria-pressed={item.area.id === areaId}
                    onClick={() => setParams({ area: item.area.id })}
                  >
                    {label('show')}
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {chosen && (
        <Stack gap="xs" component="section" aria-label={label('title', { name: chosen.area.name })}>
          <Title order={4}>{label('title', { name: chosen.area.name })}</Title>
          {queue.isError && <Alert color="red">{errorMessage(queue.error)}</Alert>}
          {queue.isLoading && <Loader aria-label={t('app.loading')} />}
          {queue.data?.length === 0 && <Text c="dimmed">{label('empty')}</Text>}
          {queue.data && queue.data.length > 0 && (
            <ComplaintsTable
              complaints={queue.data}
              label={label('title', { name: chosen.area.name })}
            />
          )}
        </Stack>
      )}
    </Stack>
  )
}
