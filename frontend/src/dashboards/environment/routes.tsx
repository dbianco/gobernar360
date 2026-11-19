import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/types'
import { BASE_PATH } from './api'
import { ParametersPage } from './ParametersPage'
import { SummaryPage } from './SummaryPage'

export default function EnvironmentRoutes() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('environment.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          <Tabs.Tab value="summary">{t('environment.tabs.summary')}</Tabs.Tab>
          <Tabs.Tab value="tracking">{t('environment.tabs.tracking')}</Tabs.Tab>
          {hasLevel(me, 'environment', 'editor') && (
            <Tabs.Tab value="entry">{t('environment.tabs.entry')}</Tabs.Tab>
          )}
          {hasLevel(me, 'environment', 'admin') && (
            <Tabs.Tab value="parameters">{t('environment.tabs.parameters')}</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route index element={<SummaryPage />} />
        <Route
          path="parameters"
          element={
            <RequireDashboard dashboardKey="environment" min="admin">
              <ParametersPage />
            </RequireDashboard>
          }
        />
        <Route path="*" element={<Navigate to={BASE_PATH} replace />} />
      </Routes>
    </Stack>
  )
}
