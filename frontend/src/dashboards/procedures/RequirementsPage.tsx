import { Alert, Button, Group, Loader, Modal, Stack, Table, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { HelpTh } from '../../platform/HelpTh'
import { hasLevel } from '../../platform/types'
import { KEY, send, useAction, useRequirements, useSources } from './api'
import { RequirementForm } from './RequirementForm'
import { RowActions } from './RowActions'
import type { Requirement } from './types'
import { Pager } from '../../platform/Pager'
import { useLocalTable } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** The municipality's single list of what procedures ask for, each with its source. */
export function RequirementsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  // One catalog: searched and paged here, like the other catalogs.
  const requirements = useRequirements()
  const sources = useSources()
  const action = useAction()
  const [editing, setEditing] = useState<Requirement | 'new' | null>(null)
  const canEdit = hasLevel(me, KEY, 'editor')
  const label = (key: string, options = {}) => t(`procedures.requirements.${key}`, options)
  const help = (key: string) => t(`procedures.help.requirementsPage.${key}`)
  const table = useLocalTable(
    'procedures.requirements',
    requirements.data,
    (requirement) => `${requirement.name} ${requirement.source?.name ?? ''}`,
  )

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={label('searchHint')}
        />
        {canEdit && <Button onClick={() => setEditing('new')}>{label('add')}</Button>}
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      {requirements.isLoading && <Loader aria-label={t('app.loading')} />}
      {requirements.isError && <Alert color="red">{errorMessage(requirements.error)}</Alert>}
      {requirements.data?.length === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {table.hasItems && table.total === 0 && <Text c="dimmed">{label('noMatches')}</Text>}
      {table.rows.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('name')}>{label('name')}</HelpTh>
                <HelpTh help={help('source')}>{label('source')}</HelpTh>
                <HelpTh help={help('level')}>{label('level')}</HelpTh>
                <HelpTh help={help('usage')} ta="right">
                  {label('usage')}
                </HelpTh>
                {canEdit && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((requirement) => (
                <Table.Tr key={requirement.id}>
                  <Table.Td>
                    <Text size="sm">{requirement.name}</Text>
                    {requirement.description && (
                      <Text size="xs" c="dimmed">
                        {requirement.description}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>{requirement.source?.name ?? label('noSource')}</Table.Td>
                  <Table.Td>
                    {requirement.source
                      ? t(`procedures.levels.${requirement.source.level}`)
                      : t('app.none')}
                  </Table.Td>
                  <Table.Td ta="right">{requirement.procedure_count}</Table.Td>
                  {canEdit && (
                    <Table.Td>
                      <RowActions
                        editLabel={label('editNamed', { name: requirement.name })}
                        deleteLabel={label('deleteNamed', { name: requirement.name })}
                        onEdit={() => setEditing(requirement)}
                        onDelete={() =>
                          void action.run(() => send('DELETE', `/requirements/${requirement.id}`))
                        }
                      />
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Pager {...table.pager} />
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label(editing === 'new' ? 'addTitle' : 'editTitle')}
      >
        {editing !== null && (
          <RequirementForm
            sources={sources.data ?? []}
            requirement={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
