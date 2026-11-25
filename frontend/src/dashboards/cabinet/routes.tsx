import { Stack, Tabs, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { RequireDashboard } from '../../platform/RequireDashboard'
import { BASE_PATH, KEY } from './api'
import { CommitmentsPage } from './CommitmentsPage'
import { MeetingPage } from './MeetingPage'
import { MeetingsPage } from './MeetingsPage'
import { PrepareMeetingPage } from './PrepareMeetingPage'
import { SummaryPage } from './SummaryPage'

const SECTIONS = ['summary', 'meetings', 'commitments'] as const

export default function CabinetRoutes() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.slice(BASE_PATH.length).split('/')[1] || 'summary'

  return (
    <Stack>
      <Title order={2}>{t('cabinet.title')}</Title>
      <Tabs
        value={section}
        onChange={(value) => navigate(value === 'summary' ? BASE_PATH : `${BASE_PATH}/${value}`)}
      >
        <Tabs.List>
          {SECTIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`cabinet.tabs.${key}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route index element={<SummaryPage />} />
        <Route path="meetings" element={<MeetingsPage />} />
        <Route
          path="meetings/new"
          element={
            <RequireDashboard dashboardKey={KEY} min="editor">
              <PrepareMeetingPage />
            </RequireDashboard>
          }
        />
        <Route path="meetings/:id" element={<MeetingPage />} />
        <Route path="commitments" element={<CommitmentsPage />} />
        <Route path="*" element={<Navigate to={BASE_PATH} replace />} />
      </Routes>
    </Stack>
  )
}
