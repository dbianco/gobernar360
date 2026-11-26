import { Center, Loader } from '@mantine/core'
import { lazy, type ReactNode, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'

import { OverviewPage } from './dashboards/overview/OverviewPage'
import { dashboards } from './dashboards/registry'
import { HelpPage } from './platform/HelpPage'
import { AccountPage } from './platform/AccountPage'
import { AdminRoutes } from './platform/AdminRoutes'
import { AppShell } from './platform/AppShell'
import { useAuth } from './platform/authContext'
import { CommitmentPage } from './platform/commitments/CommitmentPage'
import { CommitmentsPage } from './platform/commitments/CommitmentsPage'
import { NotificationsPage } from './platform/commitments/NotificationsPage'
import { ForgotPasswordPage } from './platform/ForgotPasswordPage'
import { LoginPage } from './platform/LoginPage'
import { MunicipalityPage } from './platform/MunicipalityPage'
import { OperatorPage } from './platform/OperatorPage'
import { PublicationPage } from './platform/publication/PublicationPage'
import { ReportsPage } from './platform/reports/ReportsPage'
import { RequireDashboard } from './platform/RequireDashboard'
import { SetPasswordPage } from './platform/SetPasswordPage'
import { activeMembership } from './platform/access'
import { type Me } from './platform/types'
import { PublicPage } from './public/PublicPage'

// Loaded on demand: it brings the email editor, which is large.
const MunicipalitySettingsPage = lazy(() => import('./platform/MunicipalitySettingsPage'))

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

function MovedCommitment() {
  const { id } = useParams()
  return <Navigate to={`/commitments/${id}`} replace />
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
      {/* Open to anyone: reads only what the municipality published. */}
      <Route path="/p/:slug" element={<PublicPage />} />
      <Route element={<SignedIn />}>
        <Route index element={<OverviewPage />} />
        <Route path="account" element={<AccountPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="commitments" element={<CommitmentsPage />} />
        <Route path="commitments/:id" element={<CommitmentPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        {/* Where they were while commitments belonged to the cabinet. */}
        <Route path="d/cabinet/mine" element={<Navigate to="/commitments" replace />} />
        <Route path="d/cabinet/commitments/:id" element={<MovedCommitment />} />
        <Route
          path="admin/*"
          element={
            <Only when={(me) => activeMembership(me)?.is_admin === true}>
              <AdminRoutes />
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
        <Route
          path="platform/municipalities/:id/settings/*"
          element={
            <Only when={(me) => me.user.is_platform_operator}>
              <Suspense fallback={<PageLoader />}>
                <MunicipalitySettingsPage />
              </Suspense>
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
