import { Alert, Anchor, Button, Fieldset, Group, SimpleGrid, Stack, TextInput } from '@mantine/core'
import { type FormEvent, type ReactNode, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { DateField } from '../DateField'
import { errorMessage } from '../errorMessage'
import { cuilHasDni, normaliseCuil, normaliseDni, validCuil, validDni } from './documents'
import type { DocumentQuery, Lookup, Person, PersonBody } from './types'

const COMMON_FIELDS = [
  'first_name',
  'last_name',
  'dni',
  'cuil',
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

/** The document to look somebody up by, and what tells it from any other. */
function documentOf(common: Common): { key: string; query: DocumentQuery } | null {
  const dni = normaliseDni(common.dni)
  if (dni !== '') return { key: `dni ${dni}`, query: { dni } }
  const cuil = normaliseCuil(common.cuil)
  return cuil === '' ? null : { key: `cuil ${cuil}`, query: { cuil } }
}

/**
 * The registry part of a dashboard's person form: add a person, or edit one.
 * When adding, the document (or the CUIL, of somebody without one) is looked up in the
 * municipality's registry first so the same person is not loaded twice. `children` are the dashboard's own fields.
 */
export function RegistryPersonForm(props: {
  /** The person being edited; absent when adding. */
  person?: Person
  lookup: (document: DocumentQuery) => Promise<Lookup>
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
  const [cuilError, setCuilError] = useState<'cuilInvalid' | 'cuilMismatch' | null>(null)
  // What the registry was last asked about, and what it answered.
  const [lookup, setLookup] = useState<{ key: string; result: Lookup } | null>(null)
  const [lookupError, setLookupError] = useState<string | null>(null)
  const label = (key: string, options = {}) => t(`people.${key}`, options)
  // What the form held before the registry's data replaced it, and for which document.
  const [filled, setFilled] = useState<{ key: string; before: Common } | null>(null)
  // What is typed right now, readable after a lookup comes back.
  const typed = useRef(common)
  const set = (field: CommonField) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setCommon((current) => ({ ...current, [field]: value }))
  }
  function show(next: Common) {
    typed.current = next
    setCommon(next)
  }
  const changeDocument =
    (field: 'dni' | 'cuil') => (event: { currentTarget: { value: string } }) => {
      const next = { ...common, [field]: event.currentTarget.value }
      // Said again when leaving the field if it is still wrong. Going away only then, the
      // problem would move the button to save from under the pointer that is pressing it.
      setDniInvalid(false)
      setCuilError(null)
      if (filled && documentOf(next)?.key !== filled.key) {
        // Another document is another person: the registry's data must not stay behind.
        show({ ...filled.before, [field]: next[field] })
        setFilled(null)
      } else {
        show(next)
      }
    }
  const known = lookup !== null && lookup.key === documentOf(common)?.key ? lookup.result : null

  /** Whether what was typed may be a document and a CUIL, and of the same person. */
  function checkTyped(): boolean {
    const dni = normaliseDni(common.dni)
    const cuil = normaliseCuil(common.cuil)
    const badDni = dni !== '' && !validDni(dni)
    const badCuil = cuil !== '' && !validCuil(cuil)
    const mismatch = !badDni && !badCuil && dni !== '' && cuil !== '' && !cuilHasDni(cuil, dni)
    setDniInvalid(badDni)
    setCuilError(badCuil ? 'cuilInvalid' : mismatch ? 'cuilMismatch' : null)
    return !badDni && !badCuil && !mismatch
  }

  /** Whether the form may be saved as it is. */
  async function checkDocument(): Promise<boolean> {
    if (!checkTyped()) return false
    const document = documentOf(common)
    if (editing || document === null) return true
    if (lookup?.key === document.key) return lookup.result.registered_id === null
    let result: Lookup
    try {
      result = await props.lookup(document.query)
    } catch (error) {
      setLookupError(errorMessage(error))
      return false
    }
    // It was edited while the registry answered: this answer is about another one.
    if (documentOf(typed.current)?.key !== document.key) return false
    setLookupError(null)
    setLookup({ key: document.key, result })
    if (result.person === null) return true
    // Show what the registry has and let the person review it before saving.
    if (result.registered_id === null) {
      const registry = commonValues(result.person)
      const found: Common = {
        ...registry,
        // As typed; what the registry does not have stays.
        dni: common.dni || registry.dni,
        cuil: registry.cuil || common.cuil,
      }
      // Found by CUIL, it may bring the document along, which is what it is known by then.
      const key = documentOf(found)?.key ?? document.key
      setLookup({ key, result })
      setFilled({ key, before: common })
      show(found)
    }
    return false
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!(await checkDocument())) return
    const person = {
      ...common,
      dni: normaliseDni(common.dni) || null,
      cuil: normaliseCuil(common.cuil) || null,
      birth_date: common.birth_date || null,
    }
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
              onChange={changeDocument('dni')}
              onBlur={() => void checkDocument()}
            />
            <TextInput
              label={label('cuil')}
              description={label('cuilHint')}
              inputMode="numeric"
              maxLength={15}
              error={cuilError ? label(cuilError) : undefined}
              value={common.cuil}
              onChange={changeDocument('cuil')}
              onBlur={() => void checkDocument()}
            />
            <DateField
              label={label('birthDate')}
              value={common.birth_date}
              onChange={(birth_date) => setCommon((current) => ({ ...current, birth_date }))}
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
