import {
  Alert,
  Box,
  Button,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { HelpTh } from '../../platform/HelpTh'
import { EditableList } from '../../platform/EditableList'
import { errorMessage } from '../../platform/errorMessage'
import {
  send,
  useAction,
  useActorTypes,
  useSectors,
  useToolCategories,
  useToolSubcategories,
  useTools,
} from './api'
import { ToolForm } from './ToolForm'
import type { Named, Tool } from './types'

function Section(props: { title: string; hint?: string; children: ReactNode }) {
  return (
    <Stack gap="xs" component="section">
      <Title order={4}>{props.title}</Title>
      {props.hint && (
        <Text size="sm" c="dimmed">
          {props.hint}
        </Text>
      )}
      {props.children}
    </Stack>
  )
}

/** The municipality's own lists and the tools it offers. Dashboard admins only. */
export function ParametersPage() {
  const { t } = useTranslation()
  const actorTypes = useActorTypes()
  const sectors = useSectors()
  const categories = useToolCategories()
  const subcategories = useToolSubcategories()
  const tools = useTools()
  const action = useAction()
  const [editing, setEditing] = useState<Tool | 'new' | null>(null)
  const label = (key: string, options = {}) => t(`economic.parameters.${key}`, options)

  const failed = [actorTypes, sectors, categories, subcategories, tools].find((q) => q.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (!actorTypes.data || !sectors.data || !categories.data || !subcategories.data || !tools.data) {
    return <Loader aria-label={t('app.loading')} />
  }

  const catalog = (path: string, items: Named[], addLabel: string) => (
    <EditableList
      items={items}
      addLabel={addLabel}
      onAdd={(name) => action.run(() => send('POST', path, { name }))}
      onRename={(item, name) => action.run(() => send('PATCH', `${path}/${item.id}`, { name }))}
      onDelete={(item) => action.run(() => send('DELETE', `${path}/${item.id}`))}
    />
  )

  return (
    <Stack gap="xl">
      {action.error && <Alert color="red">{action.error}</Alert>}
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="xl">
        <Section title={label('actorTypes')}>
          {catalog('/actor-types', actorTypes.data, label('newActorType'))}
        </Section>
        <Section title={label('sectors')}>
          {catalog('/sectors', sectors.data, label('newSector'))}
        </Section>
        <Section title={label('categories')} hint={label('categoriesHint')}>
          <EditableList
            items={categories.data}
            addLabel={label('newCategory')}
            onAdd={(name) => action.run(() => send('POST', '/tool-categories', { name }))}
            onRename={(item, name) =>
              action.run(() => send('PATCH', `/tool-categories/${item.id}`, { name }))
            }
            onDelete={(item) => action.run(() => send('DELETE', `/tool-categories/${item.id}`))}
            renderDetail={(category) => (
              <Box pl="lg" pb="xs">
                <EditableList
                  items={subcategories.data.filter((item) => item.category_id === category.id)}
                  addLabel={label('newSubcategoryFor', { name: category.name })}
                  onAdd={(name) =>
                    action.run(() =>
                      send('POST', '/tool-subcategories', { category_id: category.id, name }),
                    )
                  }
                  onRename={(item, name) =>
                    action.run(() => send('PATCH', `/tool-subcategories/${item.id}`, { name }))
                  }
                  onDelete={(item) =>
                    action.run(() => send('DELETE', `/tool-subcategories/${item.id}`))
                  }
                  hideEmpty
                />
              </Box>
            )}
          />
        </Section>
      </SimpleGrid>

      <Stack gap="xs" component="section">
        <Group justify="space-between">
          <Title order={4}>{label('tools')}</Title>
          {categories.data.length > 0 && (
            <Button onClick={() => setEditing('new')}>{label('addTool')}</Button>
          )}
        </Group>
        {categories.data.length === 0 && <Text c="dimmed">{label('needsCategory')}</Text>}
        {categories.data.length > 0 && tools.data.length === 0 && (
          <Text c="dimmed">{label('noTools')}</Text>
        )}
        {tools.data.length > 0 && (
          <Table.ScrollContainer minWidth={640}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={t('economic.help.parametersPage.name')}>{label('name')}</HelpTh>
                  <HelpTh help={t('economic.help.parametersPage.category')}>
                    {label('category')}
                  </HelpTh>
                  <HelpTh help={t('economic.help.parametersPage.subcategory')}>
                    {label('subcategory')}
                  </HelpTh>
                  <HelpTh help={t('economic.help.parametersPage.audience')}>
                    {label('audience')}
                  </HelpTh>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {tools.data.map((tool) => (
                  <Table.Tr key={tool.id}>
                    <Table.Td>{tool.name}</Table.Td>
                    <Table.Td>{tool.category.name}</Table.Td>
                    <Table.Td>{tool.subcategory?.name ?? t('app.none')}</Table.Td>
                    <Table.Td>{t(`economic.audiences.${tool.audience}`)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="default"
                          aria-label={label('editNamed', { name: tool.name })}
                          onClick={() => setEditing(tool)}
                        >
                          {t('app.edit')}
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          aria-label={label('deleteNamed', { name: tool.name })}
                          onClick={() => void action.run(() => send('DELETE', `/tools/${tool.id}`))}
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
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label(editing === 'new' ? 'addTool' : 'editTool')}
      >
        {editing !== null && (
          <ToolForm
            categories={categories.data}
            subcategories={subcategories.data}
            tool={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
