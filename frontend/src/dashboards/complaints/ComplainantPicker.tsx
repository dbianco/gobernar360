import { Alert, Button, Group, SegmentedControl, SimpleGrid, Stack, TextInput } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { formatDni } from '../../platform/format'
import { type Complainant, currentLookup, type NewPerson, validDni } from './complainant'

/**
 * Who complains: anonymous, or a resident found in the municipality's registry by their
 * exact document number. Someone not found is added to the registry with the complaint.
 */
export function ComplainantPicker(props: {
  value: Complainant
  onChange: (value: Complainant) => void
  onLookup: () => void
  looking: boolean
  error: string | null
}) {
  const { t } = useTranslation()
  const { value, onChange } = props
  const label = (key: string, options = {}) => t(`complaints.form.${key}`, options)
  const known = currentLookup(value)
  const setPerson = (field: keyof NewPerson) => (event: { currentTarget: { value: string } }) =>
    onChange({ ...value, newPerson: { ...value.newPerson, [field]: event.currentTarget.value } })
  const dniInvalid = value.dni !== '' && !validDni(value.dni)

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
              maxLength={12}
              required
              withAsterisk={false}
              error={dniInvalid ? t('people.dniInvalid') : undefined}
              value={value.dni}
              onChange={(event) => onChange({ ...value, dni: event.currentTarget.value })}
            />
            <Button
              variant="default"
              loading={props.looking}
              disabled={!validDni(value.dni)}
              onClick={props.onLookup}
            >
              {label('lookup')}
            </Button>
          </Group>
          {props.error && <Alert color="red">{props.error}</Alert>}
          {known?.person && (
            <Alert color="blue">
              {label('found', {
                name: known.person.full_name,
                dni: formatDni(known.person.dni),
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
