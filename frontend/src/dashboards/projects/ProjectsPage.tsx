import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  Progress,
  Stack,
  Table,
  Text,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatPercent } from '../../platform/format'
import { hasLevel } from '../../platform/types'
import { useProjects } from './api'
import { FilterBar } from './FilterBar'
import { ProjectForm } from './ProjectForm'
import { StatusBadge } from './StatusBadge'
import { useTerm } from './termContext'
import type { ProjectFilters } from './types'

/** Filterable list of the term's projects. */
export function ProjectsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { term } = useTerm()
  const [filters, setFilters] = useState<ProjectFilters>({})
  const [creating, setCreating] = useState(false)
  const projects = useProjects(term.id, filters)
  const canEdit = hasLevel(me, 'projects', 'editor')

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <FilterBar filters={filters} onChange={setFilters} withStatus />
        {canEdit && <Button onClick={() => setCreating(true)}>{t('projects.list.create')}</Button>}
      </Group>
      {projects.isLoading && <Loader aria-label={t('app.loading')} />}
      {projects.isError && <Alert color="red">{errorMessage(projects.error)}</Alert>}
      {projects.data?.length === 0 && <Text c="dimmed">{t('projects.list.empty')}</Text>}
      {projects.data && projects.data.length > 0 && (
        <Table.ScrollContainer minWidth={720}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('projects.list.name')}</Table.Th>
                <Table.Th>{t('projects.filters.axis')}</Table.Th>
                <Table.Th>{t('projects.filters.department')}</Table.Th>
                <Table.Th>{t('projects.filters.owner')}</Table.Th>
                <Table.Th>{t('projects.filters.priority')}</Table.Th>
                <Table.Th>{t('projects.filters.status')}</Table.Th>
                <Table.Th>{t('projects.list.progress')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {projects.data.map((project) => (
                <Table.Tr key={project.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`/d/projects/projects/${project.id}`}>
                      {project.name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{project.axis.name}</Table.Td>
                  <Table.Td>{project.department.name}</Table.Td>
                  <Table.Td>{project.owner?.full_name ?? t('app.none')}</Table.Td>
                  <Table.Td>{project.priority}</Table.Td>
                  <Table.Td>
                    <StatusBadge status={project.effective_status} />
                  </Table.Td>
                  <Table.Td miw={130}>
                    <Group gap="xs" wrap="nowrap">
                      <Progress value={project.progress} w={70} aria-hidden />
                      <Text size="sm">{formatPercent(project.progress)}</Text>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title={t('projects.form.createTitle')}
        size="lg"
      >
        {creating && (
          <ProjectForm onSaved={() => setCreating(false)} onCancel={() => setCreating(false)} />
        )}
      </Modal>
    </Stack>
  )
}
