import {
  Alert,
  Anchor,
  Button,
  Fieldset,
  Group,
  NativeSelect,
  SimpleGrid,
  Stack,
  TextInput,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { errorMessage } from '../../platform/errorMessage'
import { BASE_PATH, get, send, useAction } from './api'
import { EMPLOYMENT_STATUSES, type EconomicPerson, type Lookup, type Person } from './types'

const COMMON_FIELDS = [
  'first_name',
  'last_name',
  'dni',
  'birth_date',
  'phone',
  'email',
  'address',
  'neighborhood',
] as const
type CommonField = (typeof COMMON_FIELDS)[number]
type Common = Record<CommonField, string>

const commonValues = (person?: Person): Common =>
  Object.fromEntries(COMMON_FIELDS.map((field) => [field, person?.[field] ?? ''])) as Common

const normaliseDni = (value: string) => value.replace(/[.\s]/g, '')

/**
 * Add a person to the dashboard, or edit one. When adding, the document is looked
 * up in the municipality's registry first so the same person is not loaded twice.
 */
export function PersonForm(props: { person?: EconomicPerson; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.person
  const [common, setCommon] = useState<Common>(() => commonValues(editing?.person))
  const [status, setStatus] = useState<string>(editing?.employment_status ?? 'unknown')
  const [occupation, setOccupation] = useState(editing?.occupation ?? '')
  const [dniInvalid, setDniInvalid] = useState(false)
  // The document the registry was last asked about, and what it answered.
  const [lookup, setLookup] = useState<{ dni: string; result: Lookup } | null>(null)
  const [lookupError, setLookupError] = useState<string | null>(null)
  const label = (key: string, options = {}) => t(`economic.people.${key}`, options)
  const set = (field: CommonField) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setCommon((current) => ({ ...current, [field]: value }))
  }
  const dni = normaliseDni(common.dni)
  const known = lookup?.dni === dni ? lookup.result : null

  /** Whether the form may be saved as it is. */
  async function checkDni(): Promise<boolean> {
    const invalid = dni !== '' && !/^\d{6,9}$/.test(dni)
    setDniInvalid(invalid)
    if (invalid) return false
    if (editing || dni === '') return true
    if (lookup?.dni === dni) return lookup.result.registered_id === null
    let result: Lookup
    try {
      result = await get<Lookup>('/people/lookup', { dni })
    } catch (error) {
      setLookupError(errorMessage(error))
      return false
    }
    setLookupError(null)
    setLookup({ dni, result })
    if (result.person === null) return true
    // Show what the registry has and let the person review it before saving.
    setCommon({ ...commonValues(result.person), dni: common.dni })
    return false
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!(await checkDni())) return
    const body = {
      person: { ...common, dni: dni || null, birth_date: common.birth_date || null },
      employment_status: status,
      occupation,
    }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/people/${editing.id}`, body) : send('POST', '/people', body),
    )
    if (saved) props.onDone()
  }

  const text = (field: CommonField, key: string, maxLength: number, required = false) => (
    <TextInput
      label={label(key)}
      required={required}
      withAsterisk={false}
      maxLength={maxLength}
      value={common[field]}
      onChange={set(field)}
    />
  )

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {lookupError && <Alert color="red">{lookupError}</Alert>}
        {known?.registered_id && known.person && (
          <Alert color="yellow">
            {label('alreadyRegistered', { name: known.person.full_name })}{' '}
            <Anchor component={Link} to={`${BASE_PATH}/people/${known.registered_id}`}>
              {label('openExisting')}
            </Anchor>
          </Alert>
        )}
        {known?.person && !known.registered_id && (
          <Alert color="blue">{label('inRegistry', { name: known.person.full_name })}</Alert>
        )}
        <Fieldset legend={editing ? label('commonHint') : undefined} variant="unstyled">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput
              label={label('dni')}
              description={editing ? undefined : label('dniHint')}
              inputMode="numeric"
              maxLength={12}
              error={dniInvalid ? label('dniInvalid') : undefined}
              value={common.dni}
              onChange={set('dni')}
              onBlur={() => void checkDni()}
            />
            <TextInput
              label={label('birthDate')}
              type="date"
              value={common.birth_date}
              onChange={set('birth_date')}
            />
            {text('first_name', 'firstName', 100, true)}
            {text('last_name', 'lastName', 100, true)}
            {text('phone', 'phone', 50)}
            {text('email', 'email', 200)}
            {text('address', 'address', 200)}
            {text('neighborhood', 'neighborhood', 100)}
          </SimpleGrid>
        </Fieldset>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NativeSelect
            label={label('employmentStatus')}
            value={status}
            onChange={(event) => setStatus(event.currentTarget.value)}
            data={EMPLOYMENT_STATUSES.map((value) => ({
              value,
              label: t(`economic.employmentStatuses.${value}`),
            }))}
          />
          <TextInput
            label={label('occupation')}
            maxLength={200}
            value={occupation}
            onChange={(event) => setOccupation(event.currentTarget.value)}
          />
        </SimpleGrid>
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending} disabled={Boolean(known?.registered_id)}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
