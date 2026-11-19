import { NativeSelect } from '@mantine/core'
import { useTranslation } from 'react-i18next'

const YEARS_BACK = 10

export const currentYear = () => new Date().getFullYear()

/** Chooses the year being looked at: next year down to ten years ago. */
export function YearSelect(props: { value: number; onChange: (year: number) => void }) {
  const { t } = useTranslation()
  const newest = currentYear() + 1
  const years = Array.from({ length: YEARS_BACK + 2 }, (_, index) => String(newest - index))

  return (
    <NativeSelect
      label={t('app.year')}
      value={String(props.value)}
      onChange={(event) => props.onChange(Number(event.currentTarget.value))}
      data={years}
    />
  )
}
