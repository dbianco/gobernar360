import { Group, Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/types'
import { IndicatorsPage } from './IndicatorsPage'
import { ParametersPage } from './ParametersPage'
import { ProjectDetailPage } from './ProjectDetailPage'
import { ProjectsPage } from './ProjectsPage'
import { SummaryPage } from './SummaryPage'
import { TermProvider, TermSelect } from './TermProvider'

const BASE_PATH = '/d/projects'

/** Screens that show one term's plan; they need a term to exist. */
function TermScreens() {
  return (
    <TermProvider>
      <Stack>
        <Group>
          <TermSelect />
        </Group>
        <Routes>
          <Route index element={<SummaryPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:id" element={<ProjectDetailPage />} />
          <Route path="indicators" element={<IndicatorsPage />} />
          <Route path="*" element={<Navigate to={BASE_PATH} replace />} />
        </Routes>
      </Stack>
    </TermProvider>
  )
}

export default function ProjectsRoutes() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('projects.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          <Tabs.Tab value="summary">{t('projects.tabs.summary')}</Tabs.Tab>
          <Tabs.Tab value="projects">{t('projects.tabs.projects')}</Tabs.Tab>
          <Tabs.Tab value="indicators">{t('projects.tabs.indicators')}</Tabs.Tab>
          {hasLevel(me, 'projects', 'admin') && (
            <Tabs.Tab value="parameters">{t('projects.tabs.parameters')}</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
      <Routes>
        {/* Parameters stay reachable before any term exists: that is where the first one is created. */}
        <Route
          path="parameters"
          element={
            <RequireDashboard dashboardKey="projects" min="admin">
              <ParametersPage />
            </RequireDashboard>
          }
        />
        <Route path="*" element={<TermScreens />} />
      </Routes>
    </Stack>
  )
}
