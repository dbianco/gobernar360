import {
  ActionIcon,
  Anchor,
  AppShell as Shell,
  Burger,
  Group,
  NavLink,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconBuildingCommunity,
  IconFileReport,
  IconLayoutDashboard,
  IconSettings,
  IconLogout,
  IconUsers,
  IconWorld,
  type Icon,
} from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'

import { dashboards } from '../dashboards/registry'
import { useAuth } from './authContext'
import { MunicipalityChooser, MunicipalitySwitcher, NoMunicipality } from './MunicipalitySwitcher'
import { activeMembership } from './access'

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
  // Pages that do not need an active municipality.
  const onPlatformPages = ['/platform', '/account'].some((path) =>
    location.pathname.startsWith(path),
  )

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
  const link = (to: string, label: string, LinkIcon: Icon) => (
    <NavLink
      key={to}
      component={Link}
      to={to}
      label={label}
      leftSection={<LinkIcon size={20} stroke={1.5} aria-hidden />}
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
            <Anchor component={Link} to="/account" size="sm" title={t('account.link')}>
              {me.user.full_name}
            </Anchor>
            <Tooltip
              label={t('app.logout')}
              withArrow
              events={{ hover: true, focus: true, touch: true }}
            >
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                aria-label={t('app.logout')}
                onClick={() => void logout()}
              >
                <IconLogout size={20} stroke={1.5} aria-hidden />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </Shell.Header>

      <Shell.Navbar p="xs">
        {membership && link('/', t('nav.overview'), IconLayoutDashboard)}
        {membership && visibleDashboards.map((d) => link(d.basePath, t(d.labelKey), d.icon))}
        {membership?.is_admin && link('/admin/users', t('nav.users'), IconUsers)}
        {membership?.is_admin && link('/admin/settings', t('nav.settings'), IconSettings)}
        {membership?.is_admin && link('/admin/reports', t('nav.reports'), IconFileReport)}
        {membership?.is_admin &&
          link('/admin/publication', t('nav.publication'), IconWorld)}
        {isOperator && link('/platform', t('nav.platform'), IconBuildingCommunity)}
      </Shell.Navbar>

      <Shell.Main>{content}</Shell.Main>
    </Shell>
  )
}
