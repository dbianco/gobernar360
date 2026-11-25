import {
  Alert,
  Button,
  Group,
  NativeSelect,
  NumberInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, lazy, Suspense, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { useZones } from '../geo/api'
import { MapLoader } from '../geo/MapLoader'
import { OWN_MUNICIPALITY, useSettingsScope } from './scope'
import type { MapSettings, MunicipalitySettings } from './types'

const BackgroundPreview = lazy(() => import('../geo/BackgroundPreview'))

// The same limits the API has.
const MIN_THRESHOLD = 2
const MAX_THRESHOLD = 100
const KEY_PAUSE_MS = 600
const API_KEY = /^[A-Za-z0-9._-]{1,100}$/

/** The background of the maps, and which counts per zone are too small to show. */
export function MapSettingsForm({ settings }: { settings: MunicipalitySettings }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { base, settingsKey } = useSettingsScope()
  // The preview opens on the municipality's zones. The operator, who sees no data of the
  // municipality being configured, gets the whole country.
  const zones = useZones(undefined, base === OWN_MUNICIPALITY.base)
  const [key, setKey] = useState(settings.map_background)
  const [apiKey, setApiKey] = useState(settings.map_api_key ?? '')
  const [threshold, setThreshold] = useState<number | string>(settings.small_zone_threshold)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [pending, setPending] = useState(false)
  const label = (name: string, options = {}) => t(`settings.map.${name}`, options)

  const options = settings.map_backgrounds
  const chosen = options.find((option) => option.key === key) ?? options[0]
  const keyTyped = apiKey.trim()
  const keyMissing = chosen.provider !== null && keyTyped === ''
  const keyInvalid = chosen.provider !== null && keyTyped !== '' && !API_KEY.test(keyTyped)
  const validThreshold =
    typeof threshold === 'number' &&
    Number.isInteger(threshold) &&
    threshold >= MIN_THRESHOLD &&
    threshold <= MAX_THRESHOLD
  // Tried once it is typed, or the provider would be asked with every half of a key.
  const [keyToTry] = useDebouncedValue(keyTyped, KEY_PAUSE_MS)
  const preview = useMemo(() => {
    if (chosen.provider === null) return { background: chosen, api_key: null }
    // Without its key the provider would refuse every image.
    if (keyToTry !== keyTyped || !API_KEY.test(keyToTry)) return null
    return { background: chosen, api_key: keyToTry }
  }, [chosen, keyTyped, keyToTry])
  const named = (option: { key: string }) => ({
    value: option.key,
    label: label(`backgrounds.${option.key}.name`),
  })

  function choose(next: string) {
    const provider = options.find((option) => option.key === next)?.provider
    // A key is only good for the provider that gave it.
    if (provider !== chosen.provider) setApiKey('')
    setKey(next)
    setSaved(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    setPending(true)
    setError(null)
    const body: MapSettings = {
      small_zone_threshold: Number(threshold),
      map_background: chosen.key,
      map_api_key: chosen.provider === null ? null : keyTyped,
    }
    try {
      const result = await api<MunicipalitySettings>(`${base}/settings/map`, {
        method: 'PUT',
        body,
      })
      queryClient.setQueryData(settingsKey, result)
      await queryClient.invalidateQueries({ queryKey: ['map-background'] })
      setSaved(true)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <Stack>
        <Title order={3}>{label('title')}</Title>
        {saved && <Alert color="green">{t('settings.saved')}</Alert>}
        {error && <Alert color="red">{error}</Alert>}
        <NativeSelect
          label={label('background')}
          description={label('backgroundHint')}
          value={chosen.key}
          onChange={(event) => choose(event.currentTarget.value)}
          data={[
            {
              group: label('withoutKey'),
              items: options.filter((option) => option.provider === null).map(named),
            },
            {
              group: label('withKey'),
              items: options.filter((option) => option.provider !== null).map(named),
            },
          ]}
        />
        <Text size="sm">{label(`backgrounds.${chosen.key}.description`)}</Text>
        {chosen.provider !== null && (
          <TextInput
            label={label('apiKey', { provider: chosen.provider })}
            description={label('apiKeyHint', { provider: chosen.provider })}
            value={apiKey}
            error={keyInvalid ? label('apiKeyInvalid') : undefined}
            maxLength={100}
            autoComplete="off"
            onChange={(event) => {
              setApiKey(event.currentTarget.value)
              setSaved(false)
            }}
          />
        )}
        {preview && !zones.isLoading ? (
          <Suspense fallback={<MapLoader height={280} />}>
            <BackgroundPreview
              label={label('preview')}
              background={preview}
              zones={zones.data ?? []}
            />
          </Suspense>
        ) : (
          keyMissing && <Text c="dimmed">{label('previewNeedsKey')}</Text>
        )}
        <NumberInput
          label={label('threshold')}
          description={label('thresholdHint', { min: MIN_THRESHOLD, max: MAX_THRESHOLD })}
          value={threshold}
          min={MIN_THRESHOLD}
          max={MAX_THRESHOLD}
          allowDecimal={false}
          allowNegative={false}
          clampBehavior="none"
          error={
            validThreshold
              ? undefined
              : label('thresholdInvalid', { min: MIN_THRESHOLD, max: MAX_THRESHOLD })
          }
          maw={420}
          onChange={(value) => {
            setThreshold(value)
            setSaved(false)
          }}
        />
        <Group justify="flex-end">
          <Button
            type="submit"
            loading={pending}
            disabled={!validThreshold || keyMissing || keyInvalid}
          >
            {label('save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
