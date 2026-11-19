import { Alert, Anchor, Button, Fieldset, Group, SimpleGrid, Stack, TextInput } from '@mantine/core'
import { type FormEvent, type ReactNode, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { errorMessage } from '../errorMessage'
import type { Lookup, Person, PersonBody } from './types'

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
 * The registry part of a dashboard's person form: add a person, or edit one.
 * When adding, the document is looked up in the municipality's registry first
 * so the same person is not loaded twice. `children` are the dashboard's own fields.
 */
export function RegistryPersonForm(props: {
  /** The person being edited; absent when adding. */
  person?: Person
  lookup: (dni: string) => Promise<Lookup>
  /** Where the dashboard shows a person it already incorporated. */
  existingPath: (registeredId: string) => string
  save: (person: PersonBody) => Promise<unknown>
  action: {
    run: <T>(action: () => Promise<T>) => Promise<T | undefined>
    error: string | null
    pending: boolean
  }
  onDone: () => void
  children?: ReactNode
}) {
  const { t } = useTranslation()
  const editing = props.person
  const [common, setCommon] = useState<Common>(() => commonValues(editing))
  const [dniInvalid, setDniInvalid] = useState(false)
  // The document the registry was last asked about, and what it answered.
  const [lookup, setLookup] = useState<{ dni: string; result: Lookup } | null>(null)
  const [lookupError, setLookupError] = useState<string | null>(null)
  const label = (key: string, options = {}) => t(`people.${key}`, options)
  // What the form held before the registry's data replaced it, and for which document.
  const [filled, setFilled] = useState<{ dni: string; before: Common } | null>(null)
  // The document as typed right now, readable after a lookup comes back.
  const typedDni = useRef(common.dni)
  const set = (field: CommonField) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setCommon((current) => ({ ...current, [field]: value }))
  }
  function changeDni(event: { currentTarget: { value: string } }) {
    const value = event.currentTarget.value
    typedDni.current = value
    if (filled && normaliseDni(value) !== filled.dni) {
      // Another document is another person: the registry's data must not stay behind.
      setCommon({ ...filled.before, dni: value })
      setFilled(null)
    } else {
      setCommon((current) => ({ ...current, dni: value }))
    }
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
      result = await props.lookup(dni)
    } catch (error) {
      setLookupError(errorMessage(error))
      return false
    }
    // The document was edited while the registry answered: this answer is about another one.
    if (normaliseDni(typedDni.current) !== dni) return false
    setLookupError(null)
    setLookup({ dni, result })
    if (result.person === null) return true
    // Show what the registry has and let the person review it before saving.
    if (result.registered_id === null) {
      setFilled({ dni, before: common })
      setCommon({ ...commonValues(result.person), dni: common.dni })
    }
    return false
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!(await checkDni())) return
    const person = { ...common, dni: dni || null, birth_date: common.birth_date || null }
    const saved = await props.action.run(() => props.save(person))
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
        {props.action.error && <Alert color="red">{props.action.error}</Alert>}
        {lookupError && <Alert color="red">{lookupError}</Alert>}
        {known?.registered_id && known.person && (
          <Alert color="yellow">
            {label('alreadyRegistered', { name: known.person.full_name })}{' '}
            <Anchor component={Link} to={props.existingPath(known.registered_id)}>
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
              onChange={changeDni}
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
        {props.children}
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button
            type="submit"
            loading={props.action.pending}
            disabled={Boolean(known?.registered_id)}
          >
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
