import { Button, Select, Stack, Text, Title } from '@mantine/core'
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
