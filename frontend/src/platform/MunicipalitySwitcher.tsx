import { Alert, Button, Select, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from './authContext'

/** Header control to change municipality; rendered only for users who belong to several. */
export function MunicipalitySwitcher() {
  const { t } = useTranslation()
  const { me, setActiveMunicipality } = useAuth()
  if (!me) return null

  return (
    <Select
      aria-label={t('nav.municipality')}
      w={220}
      allowDeselect={false}
      data={me.memberships.map(({ municipality }) => ({
        value: municipality.id,
        label: municipality.name,
      }))}
      value={me.active_municipality_id}
      onChange={(value) => value && void setActiveMunicipality(value)}
    />
  )
}

/** Full-page prompt shown when the user belongs to several municipalities and none is active. */
export function MunicipalityChooser() {
  const { t } = useTranslation()
  const { me, setActiveMunicipality } = useAuth()

  return (
    <Stack align="center" mt="xl">
      <Title order={3}>{t('municipality.choose')}</Title>
      {me && me.suspended_municipalities.length > 0 && (
        <Alert color="yellow" maw={520}>
          {t('municipality.suspendedOthers', {
            names: me.suspended_municipalities.map((municipality) => municipality.name).join(', '),
            count: me.suspended_municipalities.length,
          })}
        </Alert>
      )}
      {me?.memberships.map(({ municipality }) => (
        <Button
          key={municipality.id}
          variant="default"
          onClick={() => void setActiveMunicipality(municipality.id)}
        >
          {municipality.name}
        </Button>
      ))}
    </Stack>
  )
}

export function NoMunicipality() {
  const { t } = useTranslation()
  return (
    <Stack align="center" mt="xl" gap="xs">
      <Title order={3}>{t('municipality.noneTitle')}</Title>
      <Text c="dimmed">{t('municipality.noneBody')}</Text>
    </Stack>
  )
}

/** Shown instead of the work area when the user's municipality is suspended. */
export function SuspendedMunicipality() {
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const [checking, setChecking] = useState(false)
  const names = me?.suspended_municipalities.map((municipality) => municipality.name) ?? []

  async function check() {
    setChecking(true)
    await refresh()
    setChecking(false)
  }

  return (
    <Stack align="center" mt="xl" gap="xs" role="alert">
      <Title order={3}>
        {t('municipality.suspendedTitle', { names: names.join(', '), count: names.length })}
      </Title>
      <Text c="dimmed" ta="center" maw={520}>
        {t('municipality.suspendedBody')}
      </Text>
      <Button variant="default" mt="sm" loading={checking} onClick={() => void check()}>
        {t('municipality.checkAgain')}
      </Button>
    </Stack>
  )
}
