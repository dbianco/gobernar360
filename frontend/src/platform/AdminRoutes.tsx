import { Center, Loader } from '@mantine/core'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes } from 'react-router-dom'

// Loaded on demand: the email editor is large and only administrators open this page.
const SettingsPage = lazy(() =>
  import('./settings/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)

/**
 * What a municipality's administrators manage: everything is in Configuración (its users and
 * zones are tabs of it). The old addresses of those two keep working.
 */
export function AdminRoutes() {
  const { t } = useTranslation()

  return (
    <Routes>
      <Route
        path="settings/*"
        element={
          <Suspense
            fallback={
              <Center mih={200}>
                <Loader aria-label={t('app.loading')} />
              </Center>
            }
          >
            <SettingsPage />
          </Suspense>
        }
      />
      <Route path="users" element={<Navigate to="/admin/settings/users" replace />} />
      <Route path="zones" element={<Navigate to="/admin/settings/maps" replace />} />
      <Route path="*" element={<Navigate to="/admin/settings" replace />} />
    </Routes>
  )
}
