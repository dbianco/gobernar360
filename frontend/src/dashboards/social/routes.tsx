import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/types'
import { BASE_PATH } from './api'
import { ParametersPage } from './ParametersPage'

const SECTIONS = [
  'summary',
  'people',
  'households',
  'deliveries',
  'interventions',
  'reports',
] as const

export default function SocialRoutes() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('social.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          {SECTIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`social.tabs.${key}`)}
            </Tabs.Tab>
          ))}
          {hasLevel(me, 'social', 'admin') && (
            <Tabs.Tab value="parameters">{t('social.tabs.parameters')}</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route index element={null} />
        <Route
          path="parameters"
          element={
            <RequireDashboard dashboardKey="social" min="admin">
              <ParametersPage />
            </RequireDashboard>
          }
        />
        <Route path="*" element={<Navigate to={BASE_PATH} replace />} />
      </Routes>
    </Stack>
  )
}
