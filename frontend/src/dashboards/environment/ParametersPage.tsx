import {
  Alert,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { HelpTh } from '../../platform/HelpTh'
import { EditableList } from '../../platform/EditableList'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber } from '../../platform/format'
import { send, useAction, useSubcategories, useVariables } from './api'
import { CATEGORIES, type Category, type Variable } from './types'
import { VariableForm } from './VariableForm'
import { Pager } from '../../platform/Pager'
import { useLocalTable } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** What the municipality measures in each category: its subcategories and variables. */
export function ParametersPage() {
  const { t } = useTranslation()
  const subcategories = useSubcategories()
  const variables = useVariables()
  const action = useAction()
  const [category, setCategory] = useState<Category>('energy')
  const [editing, setEditing] = useState<Variable | 'new' | null>(null)
  const label = (key: string) => t(`environment.parameters.${key}`)
  const ownVariables = (variables.data ?? []).filter(
    (item) => item.subcategory.category === category,
  )
  const table = useLocalTable(
    'environment.variables',
    ownVariables,
    (variable) => `${variable.name} ${variable.subcategory.name}`,
  )

  const failed = [subcategories, variables].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (!subcategories.data || !variables.data) return <Loader aria-label={t('app.loading')} />

  const ownSubcategories = subcategories.data.filter((item) => item.category === category)

  return (
    <Stack>
      <Group>
        <NativeSelect
          label={label('category')}
          value={category}
          onChange={(event) => setCategory(event.currentTarget.value as Category)}
          data={CATEGORIES.map((value) => ({
            value,
            label: t(`environment.categories.${value}`),
          }))}
        />
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}

      <Title order={4}>{label('subcategories')}</Title>
      <EditableList
        items={ownSubcategories}
        addLabel={label('newSubcategory')}
        onAdd={(name) => action.run(() => send('POST', '/subcategories', { category, name }))}
        onRename={(item, name) =>
          action.run(() => send('PATCH', `/subcategories/${item.id}`, { name }))
        }
        onDelete={(item) => action.run(() => send('DELETE', `/subcategories/${item.id}`))}
      />

      <Group justify="space-between" mt="md">
        <Title order={4}>{label('variables')}</Title>
        {ownSubcategories.length > 0 && (
          <Button onClick={() => setEditing('new')}>{label('addVariable')}</Button>
        )}
      </Group>
      {ownSubcategories.length === 0 && <Text c="dimmed">{label('needsSubcategory')}</Text>}
      {ownSubcategories.length > 0 && ownVariables.length === 0 && (
        <Text c="dimmed">{label('noVariables')}</Text>
      )}
      {table.hasItems && (
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={label('searchHint')}
        />
      )}
      {table.hasItems && table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
      {table.rows.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={t('environment.help.parametersPage.name')}>{label('name')}</HelpTh>
                <HelpTh help={t('environment.help.parametersPage.subcategory')}>
                  {label('subcategory')}
                </HelpTh>
                <HelpTh help={t('environment.help.parametersPage.frequency')}>
                  {label('frequency')}
                </HelpTh>
                <HelpTh help={t('environment.help.parametersPage.target')}>
                  {label('target')}
                </HelpTh>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((variable) => (
                <Table.Tr key={variable.id}>
                  <Table.Td>{variable.name}</Table.Td>
                  <Table.Td>{variable.subcategory.name}</Table.Td>
                  <Table.Td>{t(`environment.frequencies.${variable.frequency}`)}</Table.Td>
                  <Table.Td>
                    {variable.target === null
                      ? t('app.none')
                      : `${formatNumber(variable.target, 2)} ${variable.unit}`.trim()}
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs" justify="flex-end" wrap="nowrap">
                      <Button
                        size="compact-xs"
                        variant="default"
                        aria-label={t('environment.parameters.editNamed', { name: variable.name })}
                        onClick={() => setEditing(variable)}
                      >
                        {t('app.edit')}
                      </Button>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="red"
                        aria-label={t('environment.parameters.deleteNamed', {
                          name: variable.name,
                        })}
                        onClick={() =>
                          void action.run(() => send('DELETE', `/variables/${variable.id}`))
                        }
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
      <Pager {...table.pager} />
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label(editing === 'new' ? 'addVariable' : 'editVariable')}
      >
        {editing !== null && (
          <VariableForm
            subcategories={ownSubcategories}
            variable={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
