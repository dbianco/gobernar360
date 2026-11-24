import { Center, Loader } from '@mantine/core'
import { type ReactNode, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes } from 'react-router-dom'

import { OverviewPage } from './dashboards/overview/OverviewPage'
import { dashboards } from './dashboards/registry'
import { AccountPage } from './platform/AccountPage'
import { AppShell } from './platform/AppShell'
import { useAuth } from './platform/authContext'
import { LoginPage } from './platform/LoginPage'
import { MunicipalityPage } from './platform/MunicipalityPage'
import { OperatorPage } from './platform/OperatorPage'
import { PublicationPage } from './platform/publication/PublicationPage'
import { ReportsPage } from './platform/reports/ReportsPage'
import { RequireDashboard } from './platform/RequireDashboard'
import { activeMembership, type Me } from './platform/types'
import { UsersAdminPage } from './platform/UsersAdminPage'
import { PublicPage } from './public/PublicPage'

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

function Only({ when, children }: { when: (me: Me) => boolean; children: ReactNode }) {
  const { me } = useAuth()
  if (!me || !when(me)) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  const { isLoading } = useAuth()
  if (isLoading) return <PageLoader />

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* Open to anyone: reads only what the municipality published. */}
      <Route path="/p/:slug" element={<PublicPage />} />
      <Route element={<SignedIn />}>
        <Route index element={<OverviewPage />} />
        <Route path="account" element={<AccountPage />} />
        <Route
          path="admin/users"
          element={
            <Only when={(me) => activeMembership(me)?.is_admin === true}>
              <UsersAdminPage />
            </Only>
          }
        />
        <Route
          path="admin/reports"
          element={
            <Only when={(me) => activeMembership(me)?.is_admin === true}>
              <ReportsPage />
            </Only>
          }
        />
        <Route
          path="admin/publication"
          element={
            <Only when={(me) => activeMembership(me)?.is_admin === true}>
              <PublicationPage />
            </Only>
          }
        />
        <Route
          path="platform"
          element={
            <Only when={(me) => me.user.is_platform_operator}>
              <OperatorPage />
            </Only>
          }
        />
        <Route
          path="platform/municipalities/:id"
          element={
            <Only when={(me) => me.user.is_platform_operator}>
              <MunicipalityPage />
            </Only>
          }
        />
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
