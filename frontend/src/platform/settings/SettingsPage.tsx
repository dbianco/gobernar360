import { Alert, Loader, Paper, Stack, Tabs, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { api } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { EmailTemplatesPanel } from './EmailTemplatesPanel'
import { GeographyForm } from './GeographyForm'
import { MapSettingsForm } from './MapSettingsForm'
import { NoticesForm } from './NoticesForm'
import { RecipientsForm } from './RecipientsForm'
import { useSettingsScope } from './scope'
import { SsoForm } from './SsoForm'
import type { MunicipalitySettings } from './types'

/**
 * What can be configured, by kind. Each tab is the last part of the address, except the
 * first, which is the address of the screen. Something that fits none goes in a "general"
 * tab, to be added before the rest when there is such a thing.
 */
const TABS = ['emails', 'access', 'maps'] as const
type Tab = (typeof TABS)[number]

const isTab = (text: string): text is Tab => (TABS as readonly string[]).includes(text)

function Section({ children }: { children: ReactNode }) {
  return (
    <Paper withBorder p="md">
      {children}
    </Paper>
  )
}

function TabContent({ tab, settings }: { tab: Tab; settings: MunicipalitySettings | undefined }) {
  if (tab === 'emails') {
    return (
      <>
        {settings && (
          <Section>
            <RecipientsForm settings={settings} />
          </Section>
        )}
        <Section>
          <NoticesForm />
        </Section>
        <Section>
          <EmailTemplatesPanel />
        </Section>
      </>
    )
  }
  if (!settings) return null
  if (tab === 'access') {
    return (
      <Section>
        <SsoForm settings={settings} />
      </Section>
    )
  }
  return (
    <>
      <Section>
        <MapSettingsForm settings={settings} />
      </Section>
      <Section>
        <GeographyForm settings={settings} />
      </Section>
    </>
  )
}

/**
 * Configuración: what a municipality's administrators set for it. The platform operator
 * sees the same screen for any municipality (see SettingsScopeContext).
 */
export function SettingsPage() {
  const { t } = useTranslation()
  const { '*': rest = '' } = useParams()
  const navigate = useNavigate()
  const { base, path, settingsKey } = useSettingsScope()
  const settings = useQuery({
    queryKey: settingsKey,
    queryFn: () => api<MunicipalitySettings>(`${base}/settings`),
  })
  const address = (tab: Tab) => (tab === TABS[0] ? path : `${path}/${tab}`)
  const known = isTab(rest)
  const tab = known ? rest : TABS[0]
  // A tab stays once opened, so that going to another one loses nothing half typed. Not
  // before: a map cannot be drawn while it is hidden.
  const [opened, setOpened] = useState<Tab[]>([tab])
  if (!opened.includes(tab)) setOpened([...opened, tab])

  if (rest !== '' && (!known || rest === TABS[0])) return <Navigate to={path} replace />

  return (
    <Stack maw={860}>
      <Title order={2}>{t('settings.title')}</Title>
      <Text c="dimmed">{t('settings.intro')}</Text>
      {settings.isLoading && <Loader aria-label={t('app.loading')} />}
      {settings.isError && <Alert color="red">{errorMessage(settings.error)}</Alert>}
      <Tabs
        variant="outline"
        value={tab}
        onChange={(value) => navigate(address((value ?? TABS[0]) as Tab))}
        // Only hidden: the default also stops the effects of what is inside, and the email
        // editor would start over with the saved text.
        keepMountedMode="display-none"
      >
        <Tabs.List aria-label={t('settings.title')}>
          {TABS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`settings.tabs.${key}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {TABS.map((key) => (
          <Tabs.Panel key={key} value={key} pt="md">
            <Stack>
              {opened.includes(key) && <TabContent tab={key} settings={settings.data} />}
            </Stack>
          </Tabs.Panel>
        ))}
      </Tabs>
    </Stack>
  )
}
