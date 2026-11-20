import { Alert, Button, Group, Loader, Modal, Stack, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { EditableList } from '../../platform/EditableList'
import { errorMessage } from '../../platform/errorMessage'
import { HelpTh } from '../../platform/HelpTh'
import { send, useAction, useAreas, useSources } from './api'
import { RowActions } from './RowActions'
import { SourceForm } from './SourceForm'
import type { Source } from './types'

/** The municipality's areas and the sources of what procedures ask for. Dashboard admins only. */
export function ParametersPage() {
  const { t } = useTranslation()
  const areas = useAreas()
  const sources = useSources()
  const action = useAction()
  const [editing, setEditing] = useState<Source | 'new' | null>(null)
  const label = (key: string, options = {}) => t(`procedures.parameters.${key}`, options)
  const help = (key: string) => t(`procedures.help.parametersPage.${key}`)

  const failed = [areas, sources].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (!areas.data || !sources.data) return <Loader aria-label={t('app.loading')} />

  return (
    <Stack gap="xl">
      {action.error && <Alert color="red">{action.error}</Alert>}
      <Stack gap="xs" component="section" maw={480}>
        <Title order={4}>{label('areas')}</Title>
        <Text size="sm" c="dimmed">
          {label('areasHint')}
        </Text>
        <EditableList
          items={areas.data}
          addLabel={label('newArea')}
          onAdd={(name) => action.run(() => send('POST', '/areas', { name }))}
          onRename={(item, name) => action.run(() => send('PATCH', `/areas/${item.id}`, { name }))}
          onDelete={(item) => action.run(() => send('DELETE', `/areas/${item.id}`))}
        />
      </Stack>

      <Stack gap="xs" component="section">
        <Group justify="space-between">
          <div>
            <Title order={4}>{label('sources')}</Title>
            <Text size="sm" c="dimmed">
              {label('sourcesHint')}
            </Text>
          </div>
          <Button onClick={() => setEditing('new')}>{label('addSource')}</Button>
        </Group>
        {sources.data.length === 0 && <Text c="dimmed">{label('noSources')}</Text>}
        {sources.data.length > 0 && (
          <Table.ScrollContainer minWidth={560}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={help('name')}>{label('name')}</HelpTh>
                  <HelpTh help={help('level')}>{label('level')}</HelpTh>
                  <HelpTh help={help('area')}>{label('area')}</HelpTh>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sources.data.map((source) => (
                  <Table.Tr key={source.id}>
                    <Table.Td>{source.name}</Table.Td>
                    <Table.Td>{t(`procedures.levels.${source.level}`)}</Table.Td>
                    <Table.Td>{source.area?.name ?? t('app.none')}</Table.Td>
                    <Table.Td>
                      <RowActions
                        editLabel={label('editNamed', { name: source.name })}
                        deleteLabel={label('deleteNamed', { name: source.name })}
                        onEdit={() => setEditing(source)}
                        onDelete={() =>
                          void action.run(() => send('DELETE', `/sources/${source.id}`))
                        }
                      />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Stack>
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label(editing === 'new' ? 'addSource' : 'editSource')}
      >
        {editing !== null && (
          <SourceForm
            areas={areas.data}
            source={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
