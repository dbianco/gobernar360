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

import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatPercent } from '../../platform/format'
import { hasLevel } from '../../platform/access'
import { useProjects } from './api'
import { FilterBar } from './FilterBar'
import { ProjectForm } from './ProjectForm'
import { StatusBadge } from './StatusBadge'
import { useTerm } from './termContext'
import type { ProjectFilters } from './types'
import { Pager } from '../../platform/Pager'
import { useLocalTable } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** Filterable list of the term's projects. */
export function ProjectsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { term } = useTerm()
  const [filters, setFilters] = useState<ProjectFilters>({})
  const [creating, setCreating] = useState(false)
  const projects = useProjects(term.id, filters)
  const table = useLocalTable('projects.projects', projects.data, (project) => project.name)
  const canEdit = hasLevel(me, 'projects', 'editor')

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end">
          <SearchInput
            value={table.query}
            onChange={table.setQuery}
            placeholder={t('projects.list.searchHint')}
          />
          <FilterBar filters={filters} onChange={setFilters} withStatus />
        </Group>
        {canEdit && <Button onClick={() => setCreating(true)}>{t('projects.list.create')}</Button>}
      </Group>
      {projects.isLoading && <Loader aria-label={t('app.loading')} />}
      {projects.isError && <Alert color="red">{errorMessage(projects.error)}</Alert>}
      {projects.data?.length === 0 && <Text c="dimmed">{t('projects.list.empty')}</Text>}
      {table.hasItems && table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
      {table.rows.length > 0 && (
        <Table.ScrollContainer minWidth={720}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={t('projects.help.projectsPage.name')}>
                  {t('projects.list.name')}
                </HelpTh>
                <HelpTh help={t('projects.help.projectsPage.axis')}>
                  {t('projects.filters.axis')}
                </HelpTh>
                <HelpTh help={t('projects.help.projectsPage.department')}>
                  {t('projects.filters.department')}
                </HelpTh>
                <HelpTh help={t('projects.help.projectsPage.owner')}>
                  {t('projects.filters.owner')}
                </HelpTh>
                <HelpTh help={t('projects.help.projectsPage.priority')}>
                  {t('projects.filters.priority')}
                </HelpTh>
                <HelpTh help={t('projects.help.projectsPage.status')}>
                  {t('projects.filters.status')}
                </HelpTh>
                <HelpTh help={t('projects.help.projectsPage.progress')}>
                  {t('projects.list.progress')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((project) => (
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
      <Pager {...table.pager} />
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
