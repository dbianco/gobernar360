import { type ComboboxItem, MultiSelect, type OptionsFilter, Select } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { normalize } from './paging'

interface Person {
  id: string
  full_name: string
}

/** Every word typed, in any order and without minding accents, as searches elsewhere. */
const byName: OptionsFilter = ({ options, search }) => {
  const words = normalize(search).split(/\s+/).filter(Boolean)
  return (options as ComboboxItem[]).filter((option) =>
    words.every((word) => normalize(option.label).includes(word)),
  )
}

const data = (people: Person[]) =>
  people.map((person) => ({ value: person.id, label: person.full_name }))

/**
 * A list of people to choose one from, narrowed by typing part of a name. `value` is the
 * person's id or '' for nobody. Lists of people always use it: municipalities have many.
 */
export function PersonSelect(props: {
  label: string
  value: string
  onChange: (id: string) => void
  people: Person[]
  /** What is shown while nobody is chosen, e.g. "everybody" in a filter. */
  placeholder?: string
  required?: boolean
}) {
  const { t } = useTranslation()
  return (
    <Select
      label={props.label}
      placeholder={props.placeholder ?? t('app.person.choose')}
      nothingFoundMessage={t('app.noMatches')}
      searchable
      clearable={!props.required}
      // Also for those who use the keyboard or a screen reader.
      clearButtonProps={{ 'aria-label': t('app.person.clear'), 'aria-hidden': false, tabIndex: 0 }}
      allowDeselect={false}
      required={props.required}
      withAsterisk={false}
      filter={byName}
      data={data(props.people)}
      value={props.value || null}
      onChange={(id) => props.onChange(id ?? '')}
    />
  )
}

/** The same, to choose several people. */
export function PeopleSelect(props: {
  label: string
  description?: string
  value: string[]
  onChange: (ids: string[]) => void
  people: Person[]
}) {
  const { t } = useTranslation()
  // Closes after each choice: left open it covers what is below, e.g. the save button, and
  // clicking there would add somebody nobody meant to.
  const [open, setOpen] = useState(false)
  return (
    <MultiSelect
      dropdownOpened={open}
      onDropdownOpen={() => setOpen(true)}
      onDropdownClose={() => setOpen(false)}
      onOptionSubmit={() => setOpen(false)}
      label={props.label}
      description={props.description}
      placeholder={props.value.length === 0 ? t('app.person.chooseSeveral') : undefined}
      nothingFoundMessage={t('app.noMatches')}
      searchable
      hidePickedOptions
      filter={byName}
      data={data(props.people)}
      value={props.value}
      onChange={props.onChange}
    />
  )
}
