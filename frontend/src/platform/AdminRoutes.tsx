import { Center, Loader, Stack, Tabs } from '@mantine/core'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { MapLoader } from './geo/MapLoader'
import { UsersAdminPage } from './UsersAdminPage'

// Loaded on demand: the email editor is large and only administrators open this page.
const SettingsPage = lazy(() =>
  import('./settings/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)

// Loaded on demand: it brings the map.
const ZonesPage = lazy(() =>
  import('./geo/ZonesPage').then((module) => ({ default: module.ZonesPage })),
)

const SECTIONS = ['users', 'zones', 'settings'] as const

/** What a municipality's administrators manage: its users, its zones and its configuration. */
export function AdminRoutes() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.split('/')[2] || 'users'

  return (
    <Stack>
      <Tabs value={section} onChange={(value) => navigate(`/admin/${value ?? 'users'}`)}>
        <Tabs.List>
          {SECTIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`admin.tabs.${key}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route path="users" element={<UsersAdminPage />} />
        <Route
          path="zones"
          element={
            <Suspense fallback={<MapLoader />}>
              <ZonesPage />
            </Suspense>
          }
        />
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
        <Route path="*" element={<Navigate to="/admin/users" replace />} />
      </Routes>
    </Stack>
  )
}
