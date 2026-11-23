import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Paper,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate, formatMoney, formatPercent } from '../../platform/format'
import { hasLevel } from '../../platform/types'
import { send, useAction, useProject } from './api'
import { MilestonesPanel } from './MilestonesPanel'
import { ProjectForm } from './ProjectForm'
import { StatusBadge } from './StatusBadge'
import { useConfirm } from '../../platform/confirmContext'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text>{children}</Text>
    </div>
  )
}

/** Everything about one project, with editing for members who load data. */
export function ProjectDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const { me } = useAuth()
  const navigate = useNavigate()
  const project = useProject(id)
  const action = useAction()
  const [editing, setEditing] = useState(false)
  const canEdit = hasLevel(me, 'projects', 'editor')
  const listPath = '/d/projects/projects'
  const data = project.data
  const label = (key: string) => t(`projects.form.${key}`)
  const confirm = useConfirm()
  const askDelete = (message: string) =>
    confirm({ message, confirmLabel: t('app.delete'), danger: true })

  async function remove(shown: NonNullable<typeof project.data>) {
    if (!(await askDelete(t('projects.detail.deleteConfirm', { name: shown.name })))) return
    const deleted = await action.run(async () => {
      await send('DELETE', `/projects/${shown.id}`)
      return true
    })
    if (deleted) navigate(listPath)
  }

  return (
    <Stack>
      <Anchor component={Link} to={listPath}>
        {t('projects.detail.back')}
      </Anchor>
      {project.isLoading && <Loader aria-label={t('app.loading')} />}
      {project.isError && <Alert color="red">{errorMessage(project.error)}</Alert>}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {data && (
        <>
          <Group justify="space-between" align="flex-start">
            <Stack gap={4}>
              <Title order={3}>{data.name}</Title>
              <Group gap="xs">
                <StatusBadge status={data.effective_status} />
                <Badge variant="outline" color="gray">
                  {t('projects.filters.priority')} {data.priority}
                </Badge>
              </Group>
            </Stack>
            {canEdit && (
              <Group gap="xs">
                <Button variant="default" onClick={() => setEditing(true)}>
                  {t('app.edit')}
                </Button>
                <Button variant="subtle" color="red" onClick={() => void remove(data)}>
                  {t('app.delete')}
                </Button>
              </Group>
            )}
          </Group>

          <Group gap="sm" wrap="nowrap">
            <Progress value={data.progress} style={{ flex: 1 }} maw={320} aria-hidden />
            <Text>
              {t('projects.list.progress')}: {formatPercent(data.progress)}
            </Text>
          </Group>

          <Text c={data.description ? undefined : 'dimmed'} style={{ whiteSpace: 'pre-wrap' }}>
            {data.description || t('projects.detail.noDescription')}
          </Text>

          <Paper withBorder p="md">
            <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
              <Field label={label('axis')}>{data.axis.name}</Field>
              <Field label={label('objective')}>{data.objective?.name ?? t('app.none')}</Field>
              <Field label={label('department')}>{data.department.name}</Field>
              <Field label={label('owner')}>{data.owner?.full_name ?? t('app.none')}</Field>
              <Field label={label('program')}>{data.program?.name ?? t('app.none')}</Field>
              <Field label={label('year')}>{data.year}</Field>
              <Field label={label('startDate')}>{formatDate(data.start_date)}</Field>
              <Field label={label('endDate')}>{formatDate(data.end_date)}</Field>
              <Field label={label('plannedBudget')}>{formatMoney(data.planned_budget)}</Field>
              <Field label={label('executedBudget')}>{formatMoney(data.executed_budget)}</Field>
              <Field label={label('sdgs')}>
                {data.sdgs.length === 0
                  ? t('app.none')
                  : data.sdgs
                      .map((number) =>
                        t('projects.sdgLabel', { number, title: t(`projects.sdg.${number}`) }),
                      )
                      .join(' · ')}
              </Field>
            </SimpleGrid>
          </Paper>

          <MilestonesPanel project={data} canEdit={canEdit} />

          <Modal
            opened={editing}
            onClose={() => setEditing(false)}
            title={t('projects.form.editTitle')}
            size="lg"
          >
            {editing && (
              <ProjectForm
                project={data}
                onSaved={() => setEditing(false)}
                onCancel={() => setEditing(false)}
              />
            )}
          </Modal>
        </>
      )}
    </Stack>
  )
}
