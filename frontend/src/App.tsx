import { Center, Loader } from '@mantine/core'
import { type ReactNode, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes } from 'react-router-dom'

import { OverviewPage } from './dashboards/overview/OverviewPage'
import { dashboards } from './dashboards/registry'
import { AccountPage } from './platform/AccountPage'
import { AdminRoutes } from './platform/AdminRoutes'
import { AppShell } from './platform/AppShell'
import { useAuth } from './platform/authContext'
import { ForgotPasswordPage } from './platform/ForgotPasswordPage'
import { LoginPage } from './platform/LoginPage'
import { MunicipalityPage } from './platform/MunicipalityPage'
import { OperatorPage } from './platform/OperatorPage'
import { RequireDashboard } from './platform/RequireDashboard'
import { SetPasswordPage } from './platform/SetPasswordPage'
import { activeMembership } from './platform/access'
import { type Me } from './platform/types'

function PageLoader() {
  const { t } = useTranslation()
  return (
    <Center mih={200}>
      <Loader aria-label={t('app.loading')} />
    </Center>
  )
}

function SignedIn() {
  // App waits for the profile before any route renders.
  const { me } = useAuth()
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
      {/* Reached from emails; they work signed in or not. */}
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/set-password" element={<SetPasswordPage />} />
      <Route element={<SignedIn />}>
        <Route index element={<OverviewPage />} />
        <Route path="account" element={<AccountPage />} />
        <Route
          path="admin/*"
          element={
            <Only when={(me) => activeMembership(me)?.is_admin === true}>
              <AdminRoutes />
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
