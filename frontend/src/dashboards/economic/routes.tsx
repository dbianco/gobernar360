import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/access'
import { ActorDetailPage } from './ActorDetailPage'
import { ActorsPage } from './ActorsPage'
import { BASE_PATH } from './api'
import { AssignmentsPage } from './AssignmentsPage'
import { ParametersPage } from './ParametersPage'
import { PeoplePage } from './PeoplePage'
import { PersonDetailPage } from './PersonDetailPage'
import { ReportsPage } from './ReportsPage'
import { SummaryPage } from './SummaryPage'

const SECTIONS = ['summary', 'actors', 'people', 'assignments', 'reports'] as const

export default function EconomicRoutes() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('economic.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          {SECTIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`economic.tabs.${key}`)}
            </Tabs.Tab>
          ))}
          {hasLevel(me, 'economic', 'admin') && (
            <Tabs.Tab value="parameters">{t('economic.tabs.parameters')}</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route index element={<SummaryPage />} />
        <Route path="actors" element={<ActorsPage />} />
        <Route path="actors/:id" element={<ActorDetailPage />} />
        <Route path="people" element={<PeoplePage />} />
        <Route path="people/:id" element={<PersonDetailPage />} />
        <Route path="assignments" element={<AssignmentsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route
          path="parameters"
          element={
            <RequireDashboard dashboardKey="economic" min="admin">
              <ParametersPage />
            </RequireDashboard>
          }
        />
        <Route path="*" element={<Navigate to={BASE_PATH} replace />} />
      </Routes>
    </Stack>
  )
}
