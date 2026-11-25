import { Alert, Badge, Button, Group, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import { formatDate } from '../../platform/format'
import { send, useAction } from './api'
import type { Milestone, Project } from './types'

function localToday(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** Milestones of a project: their due dates, which are overdue, and controls to update them. */
export function MilestonesPanel({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { t } = useTranslation()
  const action = useAction()
  const [name, setName] = useState('')
  const [dueDate, setDueDate] = useState('')

  const label = (key: string, milestone: Milestone) =>
    t(`projects.milestones.${key}`, { name: milestone.name })

  async function add(event: FormEvent) {
    event.preventDefault()
    const created = await action.run(() =>
      send('POST', `/projects/${project.id}/milestones`, { name, due_date: dueDate }),
    )
    if (created) {
      setName('')
      setDueDate('')
    }
  }

  const status = (milestone: Milestone) => {
    if (milestone.completed_on) {
      return (
        <Badge color="green" variant="light">
          {t('projects.milestones.completedOn', { date: formatDate(milestone.completed_on) })}
        </Badge>
      )
    }
    if (milestone.in_alert) {
      return (
        <Badge color="red" variant="light">
          {t('projects.milestones.inAlert')}
        </Badge>
      )
    }
    return (
      <Badge color="gray" variant="light">
        {t('projects.milestones.pending')}
      </Badge>
    )
  }

  return (
    <Stack gap="sm">
      <Title order={4}>{t('projects.milestones.title')}</Title>
      {action.error && <Alert color="red">{action.error}</Alert>}
      {project.milestones.length === 0 ? (
        <Text c="dimmed">{t('projects.milestones.empty')}</Text>
      ) : (
        <Table.ScrollContainer minWidth={480}>
          <Table>
            <Table.Tbody>
              {project.milestones.map((milestone) => (
                <Table.Tr key={milestone.id}>
                  <Table.Td>{milestone.name}</Table.Td>
                  <Table.Td>{formatDate(milestone.due_date)}</Table.Td>
                  <Table.Td>{status(milestone)}</Table.Td>
                  {canEdit && (
                    <Table.Td>
                      <Group gap="xs" justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="default"
                          aria-label={label(
                            milestone.completed_on ? 'reopenNamed' : 'completeNamed',
                            milestone,
                          )}
                          onClick={() =>
                            void action.run(() =>
                              send('PATCH', `/milestones/${milestone.id}`, {
                                completed_on: milestone.completed_on ? null : localToday(),
                              }),
                            )
                          }
                        >
                          {t(
                            milestone.completed_on
                              ? 'projects.milestones.reopen'
                              : 'projects.milestones.complete',
                          )}
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          aria-label={label('deleteNamed', milestone)}
                          onClick={() =>
                            void action.run(() => send('DELETE', `/milestones/${milestone.id}`))
                          }
                        >
                          {t('app.delete')}
                        </Button>
                      </Group>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {canEdit && (
        <form onSubmit={add}>
          <Group align="flex-end" gap="sm">
            <TextInput
              aria-label={t('projects.milestones.name')}
              placeholder={t('projects.milestones.name')}
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
            <DateField
              aria-label={t('projects.milestones.dueDate')}
              required
              value={dueDate}
              onChange={setDueDate}
            />
            <Button type="submit" variant="default" loading={action.pending}>
              {t('projects.milestones.add')}
            </Button>
          </Group>
        </form>
      )}
    </Stack>
  )
}
