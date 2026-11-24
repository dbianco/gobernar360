import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { RequireDashboard } from '../../platform/RequireDashboard'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, KEY } from './api'
import { ComplaintDetailPage } from './ComplaintDetailPage'
import { ComplaintsPage } from './ComplaintsPage'
import { ParametersPage } from './ParametersPage'
import { QueuesPage } from './QueuesPage'
import { SummaryPage } from './SummaryPage'

const SECTIONS = ['summary', 'complaints', 'queues'] as const

export default function ComplaintsRoutes() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('complaints.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          {SECTIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`complaints.tabs.${key}`)}
            </Tabs.Tab>
          ))}
          {hasLevel(me, KEY, 'admin') && (
            <Tabs.Tab value="parameters">{t('complaints.tabs.parameters')}</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route index element={<SummaryPage />} />
        <Route path="complaints" element={<ComplaintsPage />} />
        <Route path="complaints/:id" element={<ComplaintDetailPage />} />
        <Route path="queues" element={<QueuesPage />} />
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
