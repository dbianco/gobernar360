import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  Loader,
  NumberInput,
  Paper,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { indicatorLabelKey } from '../indicators/format'
import { useAction } from '../useAction'

interface IndicatorChoice {
  key: string
  name: string
  unit: string | null
  aggregate: boolean
  published: boolean
}

interface DashboardChoice {
  key: string
  name: string
  published: boolean
  indicators: IndicatorChoice[]
}

interface Publication {
  enabled: boolean
  slug: string
  small_count_threshold: number
  dashboards: DashboardChoice[]
}

const KEY = 'publication'

function SettingsForm(props: {
  publication: Publication
  run: ReturnType<typeof useAction>['run']
}) {
  const { t } = useTranslation()
  const [enabled, setEnabled] = useState(props.publication.enabled)
  const [slug, setSlug] = useState(props.publication.slug)
  const [threshold, setThreshold] = useState<number | string>(
    props.publication.small_count_threshold,
  )
  const [saved, setSaved] = useState(false)
  const label = (key: string) => t(`publication.${key}`)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    const done = await props.run(() =>
      api(`/publication/settings`, {
        method: 'PUT',
        body: { enabled, slug, small_count_threshold: Number(threshold) },
      }),
    )
    setSaved(done !== undefined)
  }

  return (
    <Paper withBorder p="md" component="section" aria-label={label('pageSection')}>
      <form onSubmit={(event) => void submit(event)}>
        <Stack maw={520}>
          <Title order={4}>{label('pageSection')}</Title>
          <Switch
            label={label('enabled')}
            checked={enabled}
            onChange={(event) => setEnabled(event.currentTarget.checked)}
          />
          <TextInput
            label={label('slug')}
            description={label('slugHint')}
            leftSection={<Text size="sm">/p/</Text>}
            leftSectionWidth={36}
            required
            value={slug}
            onChange={(event) => setSlug(event.currentTarget.value)}
          />
          <NumberInput
            label={label('threshold')}
            description={label('thresholdHint')}
            min={0}
            max={1000}
            allowDecimal={false}
            required
            value={threshold}
            onChange={setThreshold}
          />
          <Group>
            <Button type="submit">{label('save')}</Button>
            {saved && <Text size="sm">{label('saved')}</Text>}
            {props.publication.enabled && (
              <Anchor component={Link} to={`/p/${props.publication.slug}`} target="_blank">
                {label('open')}
              </Anchor>
            )}
          </Group>
        </Stack>
      </form>
    </Paper>
  )
}

/**
 * What the municipality shows on its public page, for its administrators: the page itself,
 * each dashboard's lights and each aggregate indicator. Every choice applies at once.
 */
export function PublicationPage() {
  const { t } = useTranslation()
  const publication = useQuery({
    queryKey: [KEY],
    queryFn: () => api<Publication>('/publication'),
  })
  const action = useAction([KEY])
  const label = (key: string, options = {}) => t(`publication.${key}`, options)
  const data = publication.data
  const choose = (kind: 'dashboards' | 'indicators', key: string, published: boolean) =>
    void action.run(() =>
      api(`/publication/${kind}/${key}`, { method: 'PUT', body: { published } }),
    )

  return (
    <Stack>
      <Title order={2}>{label('title')}</Title>
      <Text size="sm" c="dimmed" maw={820}>
        {label('intro')}
      </Text>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {publication.isLoading && <Loader aria-label={t('app.loading')} />}
      {publication.isError && <Alert color="red">{errorMessage(publication.error)}</Alert>}
      {data && (
        <>
          {/* Keyed so a saved change starts the form from what the server kept. */}
          <SettingsForm
            key={`${data.enabled}/${data.slug}/${data.small_count_threshold}`}
            publication={data}
            run={action.run}
          />
          <Stack gap="sm" component="section" aria-label={label('whatSection')}>
            <Title order={4}>{label('whatSection')}</Title>
            {!data.enabled && <Text size="sm" c="dimmed">{label('needsPage')}</Text>}
            {data.dashboards.map((dashboard) => (
              <Paper key={dashboard.key} withBorder p="md">
                <Stack gap="xs">
                  <Switch
                    label={label('dashboard', {
                      name: t(`${dashboard.key}.title`, dashboard.name),
                    })}
                    description={label('dashboardHint')}
                    checked={dashboard.published}
                    disabled={action.pending}
                    onChange={(event) =>
                      choose('dashboards', dashboard.key, event.currentTarget.checked)
                    }
                  />
                  <Stack gap={6} pl="xl">
                    {dashboard.indicators.map((indicator) => {
                      const name = t(indicatorLabelKey(indicator.key), indicator.name)
                      return (
                        <Checkbox
                          key={indicator.key}
                          label={label('indicator', { name })}
                          description={indicator.aggregate ? undefined : label('notAggregate')}
                          checked={indicator.published}
                          disabled={
                            !dashboard.published || !indicator.aggregate || action.pending
                          }
                          onChange={(event) =>
                            choose('indicators', indicator.key, event.currentTarget.checked)
                          }
                        />
                      )
                    })}
                  </Stack>
                </Stack>
              </Paper>
            ))}
          </Stack>
        </>
      )}
    </Stack>
  )
}
