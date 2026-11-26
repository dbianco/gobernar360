import { Alert, Button, Group, SegmentedControl, SimpleGrid, Stack, TextInput } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { formatDni } from '../../platform/format'
import { documentQuery, formatCuil } from '../../platform/people/documents'
import type { DocumentQuery } from '../../platform/people/types'
import { type Complainant, cuilProblem, currentLookup, type NewPerson } from './complainant'

/**
 * Who complains: anonymous, or a resident found in the municipality's registry by their
 * exact DNI or CUIL. Someone not found is added to the registry with the complaint.
 */
export function ComplainantPicker(props: {
  value: Complainant
  onChange: (value: Complainant) => void
  onLookup: (query: DocumentQuery) => void
  looking: boolean
  error: string | null
}) {
  const { t } = useTranslation()
  const { value, onChange } = props
  const label = (key: string, options = {}) => t(`complaints.form.${key}`, options)
  const known = currentLookup(value)
  const setPerson = (field: keyof NewPerson) => (event: { currentTarget: { value: string } }) =>
    onChange({ ...value, newPerson: { ...value.newPerson, [field]: event.currentTarget.value } })
  const query = documentQuery(value.document)
  const problem = cuilProblem(value)

  return (
    <Stack gap="xs">
      <SegmentedControl
        aria-label={label('complainant')}
        value={value.anonymous ? 'anonymous' : 'identified'}
        onChange={(mode) => onChange({ ...value, anonymous: mode === 'anonymous' })}
        data={[
          { value: 'anonymous', label: label('anonymous') },
          { value: 'identified', label: label('identified') },
        ]}
      />
      {!value.anonymous && (
        <>
          <Group align="flex-end" wrap="nowrap">
            <TextInput
              label={label('dni')}
              description={label('dniHint')}
              inputMode="numeric"
              maxLength={15}
              required
              withAsterisk={false}
              error={value.document !== '' && query === null ? label('dniInvalid') : undefined}
              value={value.document}
              onChange={(event) => onChange({ ...value, document: event.currentTarget.value })}
            />
            <Button
              variant="default"
              loading={props.looking}
              disabled={query === null}
              onClick={query === null ? undefined : () => props.onLookup(query)}
            >
              {label('lookup')}
            </Button>
          </Group>
          {props.error && <Alert color="red">{props.error}</Alert>}
          {known?.person && (
            <Alert color="blue">
              {known.person.dni
                ? label('found', {
                    name: known.person.full_name,
                    dni: formatDni(known.person.dni),
                  })
                : label('foundByCuil', {
                    name: known.person.full_name,
                    cuil: formatCuil(known.person.cuil),
                  })}
            </Alert>
          )}
          {known && !known.person && (
            <>
              <Alert color="yellow">{label('notFound')}</Alert>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <TextInput
                  label={t('people.firstName')}
                  required
                  withAsterisk={false}
                  maxLength={100}
                  value={value.newPerson.first_name}
                  onChange={setPerson('first_name')}
                />
                <TextInput
                  label={t('people.lastName')}
                  required
                  withAsterisk={false}
                  maxLength={100}
                  value={value.newPerson.last_name}
                  onChange={setPerson('last_name')}
                />
                {query?.dni && (
                  <TextInput
                    label={t('people.cuil')}
                    description={t('people.cuilHint')}
                    inputMode="numeric"
                    maxLength={15}
                    error={problem ? t(`people.${problem}`) : undefined}
                    value={value.newPerson.cuil}
                    onChange={setPerson('cuil')}
                  />
                )}
                <TextInput
                  label={t('people.phone')}
                  maxLength={50}
                  value={value.newPerson.phone}
                  onChange={setPerson('phone')}
                />
                <TextInput
                  label={t('people.email')}
                  maxLength={200}
                  value={value.newPerson.email}
                  onChange={setPerson('email')}
                />
              </SimpleGrid>
            </>
          )}
        </>
      )}
    </Stack>
  )
}
