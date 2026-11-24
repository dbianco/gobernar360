import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { EditableList } from '../../platform/EditableList'
import { errorMessage } from '../../platform/errorMessage'
import { HelpTh } from '../../platform/HelpTh'
import { send, useAction, useAreas, useCalendar, useTypes, useZones } from './api'
import { CalendarPanel } from './CalendarPanel'
import { TypeForm } from './TypeForm'
import type { ComplaintType } from './types'

function Section(props: { title: string; hint: string; children: ReactNode; maw?: number }) {
  return (
    <Stack gap="xs" component="section" maw={props.maw}>
      <Title order={4}>{props.title}</Title>
      <Text size="sm" c="dimmed">
        {props.hint}
      </Text>
      {props.children}
    </Stack>
  )
}

/** Areas, zones, complaint types and the working calendar. Dashboard admins only. */
export function ParametersPage() {
  const { t } = useTranslation()
  const areas = useAreas()
  const zones = useZones()
  const types = useTypes()
  const calendar = useCalendar()
  const action = useAction()
  const [editing, setEditing] = useState<ComplaintType | 'new' | null>(null)
  const label = (key: string, options = {}) => t(`complaints.parameters.${key}`, options)
  const help = (key: string) => t(`complaints.help.types.${key}`)

  const failed = [areas, zones, types, calendar].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (!areas.data || !zones.data || !types.data || !calendar.data) {
    return <Loader aria-label={t('app.loading')} />
  }
  const catalog = (path: string) => ({
    onAdd: (name: string) => action.run(() => send('POST', `/${path}`, { name })),
    onRename: (item: { id: string }, name: string) =>
      action.run(() => send('PATCH', `/${path}/${item.id}`, { name })),
    onDelete: (item: { id: string }) => action.run(() => send('DELETE', `/${path}/${item.id}`)),
  })

  return (
    <Stack gap="xl">
      {action.error && <Alert color="red">{action.error}</Alert>}
      <Group align="flex-start" grow wrap="wrap">
        <Section title={label('areas')} hint={label('areasHint')} maw={480}>
          <EditableList items={areas.data} addLabel={label('newArea')} {...catalog('areas')} />
        </Section>
        <Section title={label('zones')} hint={label('zonesHint')} maw={480}>
          <EditableList items={zones.data} addLabel={label('newZone')} {...catalog('zones')} />
        </Section>
      </Group>

      <Stack gap="xs" component="section">
        <Group justify="space-between" align="flex-end">
          <div>
            <Title order={4}>{label('types')}</Title>
            <Text size="sm" c="dimmed">
              {label('typesHint')}
            </Text>
          </div>
          <Button disabled={areas.data.length === 0} onClick={() => setEditing('new')}>
            {label('addType')}
          </Button>
        </Group>
        {areas.data.length === 0 && <Text c="dimmed">{label('needsArea')}</Text>}
        {types.data.length === 0 && <Text c="dimmed">{label('noTypes')}</Text>}
        {types.data.length > 0 && (
          <Table.ScrollContainer minWidth={640}>
            <Table aria-label={label('types')}>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={help('name')}>{label('name')}</HelpTh>
                  <HelpTh help={help('area')}>{label('area')}</HelpTh>
                  <HelpTh help={help('target')} ta="right">
                    {label('target')}
                  </HelpTh>
                  <HelpTh help={help('active')}>{label('active')}</HelpTh>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {types.data.map((type) => (
                  <Table.Tr key={type.id}>
                    <Table.Td>{type.name}</Table.Td>
                    <Table.Td>{type.area.name}</Table.Td>
                    <Table.Td ta="right">
                      {label('targetValue', { count: type.target_days })}
                    </Table.Td>
                    <Table.Td>
                      {type.is_active ? (
                        t('app.yes')
                      ) : (
                        <Badge variant="light" color="gray" style={{ textTransform: 'none' }}>
                          {label('inactive')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs" justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="default"
                          aria-label={label('editNamed', { name: type.name })}
                          onClick={() => setEditing(type)}
                        >
                          {t('app.edit')}
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          aria-label={label('deleteNamed', { name: type.name })}
                          onClick={() => void action.run(() => send('DELETE', `/types/${type.id}`))}
                        >
                          {t('app.delete')}
                        </Button>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Stack>

      <Section title={label('calendar')} hint={label('calendarHint')}>
        <CalendarPanel key={calendar.data.weekdays.join()} calendar={calendar.data} />
      </Section>

      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label(editing === 'new' ? 'addType' : 'editType')}
      >
        {editing !== null && (
          <TypeForm
            areas={areas.data}
            type={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
