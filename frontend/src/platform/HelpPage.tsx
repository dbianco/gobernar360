import { Accordion, Badge, Group, Stack, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { activeMembership } from './access'
import { useAuth } from './authContext'

type Audience = 'admin' | 'operator'

/** The topics, in reading order. Their texts are under `guide.sections` in the locale. */
const SECTIONS: { key: string; audience?: Audience }[] = [
  { key: 'start' },
  { key: 'levels' },
  { key: 'overview' },
  { key: 'dashboards' },
  { key: 'commitments' },
  { key: 'maps' },
  { key: 'notifications' },
  { key: 'settings', audience: 'admin' },
  { key: 'reports', audience: 'admin' },
  { key: 'notices', audience: 'admin' },
  { key: 'operator', audience: 'operator' },
]

/** How to use the site. Each person reads the topics that apply to what they can do. */
export function HelpPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const isAdmin = me ? activeMembership(me)?.is_admin === true : false
  const isOperator = me?.user.is_platform_operator === true
  const visible = SECTIONS.filter(
    ({ audience }) =>
      !audience || (audience === 'admin' && isAdmin) || (audience === 'operator' && isOperator),
  )

  return (
    <Stack maw={860}>
      <Title order={2}>{t('guide.title')}</Title>
      <Text c="dimmed">{t('guide.intro')}</Text>
      <Accordion variant="separated" defaultValue="start">
        {visible.map(({ key, audience }) => {
          const paragraphs = t(`guide.sections.${key}.body`, { returnObjects: true }) as string[]
          return (
            <Accordion.Item key={key} value={key}>
              <Accordion.Control>
                <Group gap="sm">
                  <Text fw={500}>{t(`guide.sections.${key}.title`)}</Text>
                  {audience && (
                    <Badge variant="light" color="gray">
                      {t(audience === 'admin' ? 'guide.adminOnly' : 'guide.operatorOnly')}
                    </Badge>
                  )}
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Stack gap="xs">
                  {paragraphs.map((text) => (
                    <Text key={text}>{text}</Text>
                  ))}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          )
        })}
      </Accordion>
    </Stack>
  )
}
