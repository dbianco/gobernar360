import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/types'
import { ActorDetailPage } from './ActorDetailPage'
import { ActorsPage } from './ActorsPage'
import { BASE_PATH } from './api'
import { ParametersPage } from './ParametersPage'
import { PeoplePage } from './PeoplePage'
import { PersonDetailPage } from './PersonDetailPage'

const SECTIONS = ['summary', 'actors', 'people', 'assignments', 'reports'] as const
const Pending = () => null

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
        <Route index element={<Pending />} />
        <Route path="actors" element={<ActorsPage />} />
        <Route path="actors/:id" element={<ActorDetailPage />} />
        <Route path="people" element={<PeoplePage />} />
        <Route path="people/:id" element={<PersonDetailPage />} />
        <Route path="assignments" element={<Pending />} />
        <Route path="reports" element={<Pending />} />
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
