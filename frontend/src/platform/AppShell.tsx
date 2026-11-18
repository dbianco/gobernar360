import { AppShell as Shell, Burger, Button, Group, NavLink, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'

import { dashboards } from '../dashboards/registry'
import { useAuth } from './authContext'
import { MunicipalityChooser, MunicipalitySwitcher, NoMunicipality } from './MunicipalitySwitcher'
import { activeMembership } from './types'

/** Page frame for signed-in users: header, navigation limited to what they may see, content. */
export function AppShell() {
  const { t } = useTranslation()
  const { me, logout } = useAuth()
  const location = useLocation()
  const [menuOpen, menu] = useDisclosure(false)
  if (!me) return null

  const membership = activeMembership(me)
  const granted = new Set(me.dashboards.map((dashboard) => dashboard.key))
  const visibleDashboards = dashboards.filter((dashboard) => granted.has(dashboard.key))
  const isOperator = me.user.is_platform_operator
  const onPlatformPages = location.pathname.startsWith('/platform')

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
  const link = (to: string, label: string) => (
    <NavLink
      key={to}
      component={Link}
      to={to}
      label={label}
      active={isActive(to)}
      onClick={menu.close}
    />
  )


  let content = <Outlet />
  if (!membership && !onPlatformPages) {
    if (me.memberships.length > 0) content = <MunicipalityChooser />
    // Operators who belong to no municipality only have the platform page.
    else content = isOperator ? <Navigate to="/platform" replace /> : <NoMunicipality />
  }

  return (
    <Shell
      header={{ height: 56 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !menuOpen } }}
      padding="md"
    >
      <Shell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={menuOpen}
              onClick={menu.toggle}
              hiddenFrom="sm"
              size="sm"
              aria-label={t('nav.openMenu')}
            />
            <Title order={4}>{t('app.name')}</Title>
            {me.memberships.length > 1 && membership ? (
              <MunicipalitySwitcher />
            ) : (
              membership && <Text c="dimmed">{membership.municipality.name}</Text>
            )}
          </Group>
          <Group gap="sm" wrap="nowrap">
            <Text size="sm" visibleFrom="sm">
              {me.user.full_name}
            </Text>
            <Button variant="subtle" size="xs" onClick={() => void logout()}>
              {t('app.logout')}
            </Button>
          </Group>
        </Group>
      </Shell.Header>

      <Shell.Navbar p="xs">
        {membership && link('/', t('nav.overview'))}
        {membership && visibleDashboards.map((d) => link(d.basePath, t(d.labelKey)))}
        {membership?.is_admin && link('/admin/users', t('nav.users'))}
        {isOperator && link('/platform', t('nav.platform'))}
      </Shell.Navbar>

      <Shell.Main>{content}</Shell.Main>
    </Shell>
  )
}
