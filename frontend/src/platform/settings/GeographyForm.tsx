import { Alert, Button, Group, Stack, Text, TextInput, Title } from '@mantine/core'
import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { OWN_MUNICIPALITY, useSettingsScope } from './scope'
import type { Geography, MunicipalitySettings } from './types'

// The same limits the API has.
const IDECOR_KEY = /^[0-9]{6}$/
const CONAE_LAYER = /^[A-Za-z0-9:_-]{1,100}$/

/**
 * Where the municipality is in the official geographic services. The platform operator sets
 * it; its administrators only see it.
 */
export function GeographyForm({ settings }: { settings: MunicipalitySettings }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { base, settingsKey } = useSettingsScope()
  const [idecorKey, setIdecorKey] = useState(settings.idecor_key ?? '')
  const [conaeLayer, setConaeLayer] = useState(settings.conae_layer ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [pending, setPending] = useState(false)
  const label = (name: string) => t(`settings.geography.${name}`)
  const readOnly = base === OWN_MUNICIPALITY.base

  const key = idecorKey.trim()
  const layer = conaeLayer.trim()
  const keyInvalid = key !== '' && !IDECOR_KEY.test(key)
  const layerInvalid = layer !== '' && !CONAE_LAYER.test(layer)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    setPending(true)
    setError(null)
    const body: Geography = { idecor_key: key || null, conae_layer: layer || null }
    try {
      const result = await api<MunicipalitySettings>(`${base}/settings/geography`, {
        method: 'PUT',
        body,
      })
      queryClient.setQueryData(settingsKey, result)
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
        <Text size="sm">{label(readOnly ? 'introReadOnly' : 'intro')}</Text>
        {saved && <Alert color="green">{t('settings.saved')}</Alert>}
        {error && <Alert color="red">{error}</Alert>}
        <TextInput
          label={label('idecorKey')}
          description={label('idecorKeyHint')}
          value={idecorKey}
          placeholder={readOnly ? label('notSet') : undefined}
          error={keyInvalid && label('idecorKeyInvalid')}
          readOnly={readOnly}
          maw={420}
          onChange={(event) => {
            setIdecorKey(event.currentTarget.value)
            setSaved(false)
          }}
        />
        <TextInput
          label={label('conaeLayer')}
          description={label('conaeLayerHint')}
          value={conaeLayer}
          placeholder={readOnly ? label('notSet') : undefined}
          error={layerInvalid && label('conaeLayerInvalid')}
          readOnly={readOnly}
          maw={420}
          onChange={(event) => {
            setConaeLayer(event.currentTarget.value)
            setSaved(false)
          }}
        />
        {!readOnly && (
          <Group justify="flex-end">
            <Button type="submit" loading={pending} disabled={keyInvalid || layerInvalid}>
              {label('save')}
            </Button>
          </Group>
        )}
      </Stack>
    </form>
  )
}
