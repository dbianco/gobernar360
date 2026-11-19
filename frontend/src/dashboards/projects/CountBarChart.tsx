import { useTranslation } from 'react-i18next'

import { CountBarChart as PlatformCountBarChart, type CountRow } from '../../platform/CountBarChart'

export type { CountRow }

/** Number of projects per category as horizontal bars. */
export function CountBarChart({ title, rows }: { title: string; rows: CountRow[] }) {
  const { t } = useTranslation()
  return (
    <PlatformCountBarChart
      title={title}
      rows={rows}
      valueLabel={t('projects.summary.projectsCount')}
    />
  )
}
