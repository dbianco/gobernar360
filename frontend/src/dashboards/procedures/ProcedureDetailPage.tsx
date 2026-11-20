import {
  Alert,
  Anchor,
  Badge,
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
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Field } from '../../platform/Field'
import { formatNumber } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, KEY, send, useAction, useAreas, useProcedure, useRequirements } from './api'
import { costText } from './format'
import { ProcedureForm } from './ProcedureForm'
import { RequirementLinkForm } from './RequirementLinkForm'
import { RowActions } from './RowActions'
import type { RequirementLink } from './types'

type Dialog = 'edit' | 'delete' | 'add' | RequirementLink | null

/** One procedure: its data and the requirements it asks for, with the source of each. */
export function ProcedureDetailPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const procedure = useProcedure(id)
  const areas = useAreas()
  const requirements = useRequirements()
  const action = useAction()
  const [dialog, setDialog] = useState<Dialog>(null)
  const canEdit = hasLevel(me, KEY, 'editor')
  const label = (key: string, options = {}) => t(`procedures.detail.${key}`, options)
  const help = (key: string) => t(`procedures.help.procedureDetailPage.${key}`)
  const list = `${BASE_PATH}/procedures`
  const close = () => setDialog(null)

  if (procedure.isError) return <Alert color="red">{errorMessage(procedure.error)}</Alert>
  const data = procedure.data
  if (!data) return <Loader aria-label={t('app.loading')} />

  const asked = new Set(data.requirements.map((link) => link.requirement.id))
  const available = (requirements.data ?? []).filter((item) => !asked.has(item.id))
  const link = typeof dialog === 'object' ? dialog : null

  async function remove() {
    const deleted = await action.run(async () => {
      await send('DELETE', `/procedures/${id}`)
      return true
    })
    if (deleted) navigate(list)
    else close()
  }

  return (
    <Stack>
      <Anchor component={Link} to={list} size="sm">
        {label('back')}
      </Anchor>
      <Group justify="space-between" align="flex-start">
        <Group gap="sm">
          <Title order={3}>{data.name}</Title>
          {!data.is_active && (
            <Badge variant="light" color="gray">
              {t('procedures.list.inactive')}
            </Badge>
          )}
        </Group>
        {canEdit && (
          <Group gap="xs">
            <Button variant="default" onClick={() => setDialog('edit')}>
              {label('edit')}
            </Button>
            <Button variant="subtle" color="red" onClick={() => setDialog('delete')}>
              {label('delete')}
            </Button>
          </Group>
        )}
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
        <Field label={label('area')}>{data.area.name}</Field>
        <Field label={label('audience')}>{t(`procedures.audiences.${data.audience}`)}</Field>
        <Field label={label('channel')}>{t(`procedures.channels.${data.channel}`)}</Field>
        <Field label={label('cost')}>{costText(data, t('procedures.list.free'))}</Field>
        <Field label={label('days')}>
          {data.duration_days === null
            ? ''
            : t('procedures.list.daysValue', { count: data.duration_days })}
        </Field>
        <Field label={label('volume')}>
          {data.annual_volume === null ? '' : formatNumber(data.annual_volume)}
        </Field>
      </SimpleGrid>
      {data.url && (
        <Field label={label('url')}>
          {/* The API only stores http(s) addresses. */}
          <Anchor href={data.url} target="_blank" rel="noopener noreferrer">
            {data.url}
          </Anchor>
        </Field>
      )}
      {data.description && <Field label={label('description')}>{data.description}</Field>}

      <Stack gap="xs" component="section">
        <Group justify="space-between">
          <Title order={4}>{label('requirements')}</Title>
          {canEdit && <Button onClick={() => setDialog('add')}>{label('addRequirement')}</Button>}
        </Group>
        {data.requirements.length === 0 && <Text c="dimmed">{label('noRequirements')}</Text>}
        {data.requirements.length > 0 && (
          <Table.ScrollContainer minWidth={640}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={help('requirement')}>{label('requirement')}</HelpTh>
                  <HelpTh help={help('source')}>{label('source')}</HelpTh>
                  <HelpTh help={help('mandatory')}>{label('mandatory')}</HelpTh>
                  <HelpTh help={help('format')}>{label('format')}</HelpTh>
                  <HelpTh help={help('note')}>{label('note')}</HelpTh>
                  {canEdit && <Table.Th />}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.requirements.map((row) => (
                  <Table.Tr key={row.id}>
                    <Table.Td>{row.requirement.name}</Table.Td>
                    <Table.Td>
                      {row.requirement.source ? (
                        <>
                          <Text>{row.requirement.source.name}</Text>
                          <Text size="xs" c="dimmed">
                            {t(`procedures.levels.${row.requirement.source.level}`)}
                          </Text>
                        </>
                      ) : (
                        label('noSource')
                      )}
                    </Table.Td>
                    <Table.Td>{row.mandatory ? t('app.yes') : label('optional')}</Table.Td>
                    <Table.Td>{t(`procedures.formats.${row.format}`)}</Table.Td>
                    <Table.Td>{row.note || t('app.none')}</Table.Td>
                    {canEdit && (
                      <Table.Td>
                        <RowActions
                          editLabel={label('editNamed', { name: row.requirement.name })}
                          deleteLabel={label('removeNamed', { name: row.requirement.name })}
                          deleteText={label('remove')}
                          onEdit={() => setDialog(row)}
                          onDelete={() =>
                            void action.run(() =>
                              send('DELETE', `/procedures/${id}/requirements/${row.id}`),
                            )
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
      </Stack>

      <Modal opened={dialog === 'edit'} onClose={close} title={label('editTitle')} size="lg">
        {dialog === 'edit' && (
          <ProcedureForm areas={areas.data ?? []} procedure={data} onDone={close} />
        )}
      </Modal>
      <Modal opened={dialog === 'delete'} onClose={close} title={label('delete')}>
        <Stack>
          <Text>{label('confirmDelete')}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              {t('app.cancel')}
            </Button>
            <Button color="red" loading={action.pending} onClick={() => void remove()}>
              {t('app.confirm')}
            </Button>
          </Group>
        </Stack>
      </Modal>
      <Modal
        opened={dialog === 'add' || link !== null}
        onClose={close}
        title={label(link ? 'editRequirementTitle' : 'addRequirementTitle')}
      >
        {(dialog === 'add' || link) && (
          <RequirementLinkForm
            procedureId={id}
            available={available}
            link={link ?? undefined}
            onDone={close}
          />
        )}
      </Modal>
    </Stack>
  )
}
