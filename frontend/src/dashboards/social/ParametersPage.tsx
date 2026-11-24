import {
  Alert,
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
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { HelpTh } from '../../platform/HelpTh'
import { EditableList } from '../../platform/EditableList'
import { errorMessage } from '../../platform/errorMessage'
import { IndicatorTargets } from '../../platform/indicators/IndicatorTargets'
import { send, useAction, useBenefitCategories, useBenefits, useInterventionTypes } from './api'
import { BenefitForm } from './BenefitForm'
import type { Benefit, Named } from './types'

/** The municipality's own catalogs. Dashboard admins only. */
export function ParametersPage() {
  const { t } = useTranslation()
  const categories = useBenefitCategories()
  const benefits = useBenefits()
  const interventionTypes = useInterventionTypes()
  const action = useAction()
  const [editing, setEditing] = useState<Benefit | 'new' | null>(null)
  const label = (key: string, options = {}) => t(`social.parameters.${key}`, options)

  const failed = [categories, benefits, interventionTypes].find((query) => query.isError)
  if (failed) return <Alert color="red">{errorMessage(failed.error)}</Alert>
  if (!categories.data || !benefits.data || !interventionTypes.data) {
    return <Loader aria-label={t('app.loading')} />
  }

  const catalog = (title: string, path: string, items: Named[], addLabel: string) => (
    <Stack gap="xs" component="section">
      <Title order={4}>{title}</Title>
      <EditableList
        items={items}
        addLabel={addLabel}
        onAdd={(name) => action.run(() => send('POST', path, { name }))}
        onRename={(item, name) => action.run(() => send('PATCH', `${path}/${item.id}`, { name }))}
        onDelete={(item) => action.run(() => send('DELETE', `${path}/${item.id}`))}
      />
    </Stack>
  )

  return (
    <Stack gap="xl">
      {action.error && <Alert color="red">{action.error}</Alert>}
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
        {catalog(label('categories'), '/benefit-categories', categories.data, label('newCategory'))}
        {catalog(
          label('interventionTypes'),
          '/intervention-types',
          interventionTypes.data,
          label('newInterventionType'),
        )}
      </SimpleGrid>

      <Stack gap="xs" component="section">
        <Group justify="space-between">
          <Title order={4}>{label('benefits')}</Title>
          {categories.data.length > 0 && (
            <Button onClick={() => setEditing('new')}>{label('addBenefit')}</Button>
          )}
        </Group>
        {categories.data.length === 0 && <Text c="dimmed">{label('needsCategory')}</Text>}
        {categories.data.length > 0 && benefits.data.length === 0 && (
          <Text c="dimmed">{label('noBenefits')}</Text>
        )}
        {benefits.data.length > 0 && (
          <Table.ScrollContainer minWidth={560}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={t('social.help.parametersPage.name')}>{label('name')}</HelpTh>
                  <HelpTh help={t('social.help.parametersPage.category')}>
                    {label('category')}
                  </HelpTh>
                  <HelpTh help={t('social.help.parametersPage.description')}>
                    {label('description')}
                  </HelpTh>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {benefits.data.map((benefit) => (
                  <Table.Tr key={benefit.id}>
                    <Table.Td>{benefit.name}</Table.Td>
                    <Table.Td>{benefit.category.name}</Table.Td>
                    <Table.Td>{benefit.description || t('app.none')}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="default"
                          aria-label={label('editNamed', { name: benefit.name })}
                          onClick={() => setEditing(benefit)}
                        >
                          {t('app.edit')}
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          aria-label={label('deleteNamed', { name: benefit.name })}
                          onClick={() =>
                            void action.run(() => send('DELETE', `/benefits/${benefit.id}`))
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
      </Stack>
      <IndicatorTargets dashboardKey="social" />
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label(editing === 'new' ? 'addBenefit' : 'editBenefit')}
      >
        {editing !== null && (
          <BenefitForm
            categories={categories.data}
            benefit={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
