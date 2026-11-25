import { Center, Loader } from '@mantine/core'
import { useTranslation } from 'react-i18next'

/** Shown while the map code arrives. */
export function MapLoader({ height = 420 }: { height?: number }) {
  const { t } = useTranslation()
  return (
    <Center h={height}>
      <Loader aria-label={t('app.loading')} />
    </Center>
  )
}
