import { CloseButton, TextInput } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

/** The search box of a table: what it searches is said in its placeholder. */
export function SearchInput(props: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  label?: string
}) {
  const { t } = useTranslation()
  return (
    <TextInput
      type="search"
      label={props.label ?? t('app.search')}
      placeholder={props.placeholder}
      maxLength={100}
      miw={240}
      maw={360}
      leftSection={<IconSearch size={16} aria-hidden />}
      rightSection={
        props.value ? (
          <CloseButton
            size="sm"
            aria-label={t('app.clearSearch')}
            onClick={() => props.onChange('')}
          />
        ) : null
      }
      value={props.value}
      onChange={(event) => props.onChange(event.currentTarget.value)}
    />
  )
}
