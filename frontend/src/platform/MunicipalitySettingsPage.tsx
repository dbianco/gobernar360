import { Alert, Anchor, Loader, Stack, Title } from '@mantine/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { errorMessage } from './errorMessage'
import { useMunicipalities } from './operatorApi'
import { SettingsScopeContext } from './settings/scope'
import { SettingsPage } from './settings/SettingsPage'

/** Platform operator: the configuration a municipality's administrators manage, for any of them. */
export default function MunicipalitySettingsPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const municipalities = useMunicipalities()
  const municipality = municipalities.data?.find((item) => item.id === id)
  const scope = useMemo(
    () => ({
      base: `/platform/municipalities/${id}`,
      path: `/platform/municipalities/${id}/settings`,
      key: ['platform', 'municipalities', id],
      own: false,
    }),
    [id],
  )

  return (
    <Stack>
      <Anchor component={Link} to={`/platform/municipalities/${id}`}>
        {t('platform.backToMunicipality')}
      </Anchor>
      {municipalities.isLoading && <Loader aria-label={t('app.loading')} />}
      {municipalities.isError && <Alert color="red">{errorMessage(municipalities.error)}</Alert>}
      {municipalities.data && !municipality && (
        <Alert color="yellow">{t('platform.notFound')}</Alert>
      )}
      {municipality && (
        <>
          <Title order={1} size="h2">
            {municipality.name}
          </Title>
          <SettingsScopeContext.Provider value={scope}>
            {/* Remounted for another municipality, so no form keeps the previous one's values. */}
            <SettingsPage key={municipality.id} />
          </SettingsScopeContext.Provider>
        </>
      )}
    </Stack>
  )
}
