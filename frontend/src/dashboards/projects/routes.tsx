import { Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

export default function ProjectsRoutes() {
  const { t } = useTranslation()
  return <Title order={2}>{t('projects.title')}</Title>
}
