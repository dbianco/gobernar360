import { Center, Loader } from '@mantine/core'
import { Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes } from 'react-router-dom'

import { OverviewPage } from './dashboards/overview/OverviewPage'
import { dashboards } from './dashboards/registry'
import { AppShell } from './platform/AppShell'
import { useAuth } from './platform/authContext'
import { LoginPage } from './platform/LoginPage'
import { RequireDashboard } from './platform/RequireDashboard'

function PageLoader() {
  const { t } = useTranslation()
  return (
    <Center mih={200}>
      <Loader aria-label={t('app.loading')} />
    </Center>
  )
}

function SignedIn() {
  const { me, isLoading } = useAuth()
  if (isLoading) return <PageLoader />
  if (!me) return <Navigate to="/login" replace />
  return <AppShell />
}

export default function App() {
  const { isLoading } = useAuth()
  if (isLoading) return <PageLoader />

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<SignedIn />}>
        <Route index element={<OverviewPage />} />
        {dashboards.map((dashboard) => (
          <Route
            key={dashboard.key}
            path={`${dashboard.basePath}/*`}
            element={
              <RequireDashboard dashboardKey={dashboard.key}>
                <Suspense fallback={<PageLoader />}>
                  <dashboard.routes />
                </Suspense>
              </RequireDashboard>
            }
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
