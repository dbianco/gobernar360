import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, KEY } from './api'
import { ParametersPage } from './ParametersPage'
import { RequirementsPage } from './RequirementsPage'

const SECTIONS = ['summary', 'procedures', 'requirements', 'opportunities'] as const

export default function ProceduresRoutes() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('procedures.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          {SECTIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`procedures.tabs.${key}`)}
            </Tabs.Tab>
          ))}
          {hasLevel(me, KEY, 'admin') && (
            <Tabs.Tab value="parameters">{t('procedures.tabs.parameters')}</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route path="requirements" element={<RequirementsPage />} />
        <Route
          path="parameters"
          element={
            <RequireDashboard dashboardKey={KEY} min="admin">
              <ParametersPage />
            </RequireDashboard>
          }
        />
        <Route path="*" element={<Navigate to={BASE_PATH} replace />} />
      </Routes>
    </Stack>
  )
}
