import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { hasLevel } from '../../platform/types'
import { ActorForm } from './ActorForm'
import { BASE_PATH, send, useAction, useActor, usePeople } from './api'
import { AssignmentsPanel } from './AssignmentsPanel'
import { Field } from './Field'
import { formatCuit } from './format'
import { type ActorDetail, type Role, ROLES } from './types'

const MATCHES_SHOWN = 8

/** Find a person already in the dashboard and link them to the actor with a role. */
function LinkPersonPanel(props: { actor: ActorDetail; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState<Role>('owner')
  const ready = search.trim().length >= 2
  const people = usePeople({ q: search.trim(), limit: MATCHES_SHOWN }, ready)
  const label = (key: string, options = {}) => t(`economic.actors.${key}`, options)
  const linked = new Set(props.actor.people.map((link) => link.person.id))
  const matches = (people.data?.items ?? []).filter((person) => !linked.has(person.id))

  async function link(personId: string) {
    const saved = await action.run(() =>
      send('POST', `/actors/${props.actor.id}/people`, { person_id: personId, role }),
    )
    if (saved) props.onDone()
  }

  return (
    <Paper withBorder p="md">
      <Stack gap="sm">
        {action.error && <Alert color="red">{action.error}</Alert>}
        <Group align="flex-end">
          <TextInput
            label={label('findPerson')}
            description={label('findPersonHint')}
            autoFocus
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.currentTarget.value)}
          />
          <NativeSelect
            label={label('role')}
            value={role}
            onChange={(event) => setRole(event.currentTarget.value as Role)}
            data={ROLES.map((value) => ({ value, label: t(`economic.roles.${value}`) }))}
          />
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
        </Group>
        {people.isError && <Alert color="red">{errorMessage(people.error)}</Alert>}
        {ready && people.data && matches.length === 0 && (
          <Text c="dimmed">{label('noMatches')}</Text>
        )}
        {ready &&
          matches.map((person) => (
            <Group key={person.id} justify="space-between">
              <Text>{person.person.full_name}</Text>
              <Button
                size="compact-sm"
                aria-label={label('linkNamed', { name: person.person.full_name })}
                loading={action.pending}
                onClick={() => void link(person.id)}
              >
                {label('link')}
              </Button>
            </Group>
          ))}
      </Stack>
    </Paper>
  )
}

/** Everything about one economic actor: its data, its people and the tools it received. */
export function ActorDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const { me } = useAuth()
  const navigate = useNavigate()
  const actor = useActor(id)
  const action = useAction()
  const [editing, setEditing] = useState(false)
  const [linking, setLinking] = useState(false)
  const canEdit = hasLevel(me, 'economic', 'editor')
  const listPath = `${BASE_PATH}/actors`
  const data = actor.data
  const label = (key: string, options = {}) => t(`economic.actors.${key}`, options)

  async function remove() {
    if (!data || !window.confirm(label('deleteConfirm', { name: data.name }))) return
    const deleted = await action.run(async () => {
      await send('DELETE', `/actors/${data.id}`)
      return true
    })
    if (deleted) navigate(listPath)
  }

  return (
    <Stack>
      <Anchor component={Link} to={listPath}>
        {label('back')}
      </Anchor>
      {actor.isLoading && <Loader aria-label={t('app.loading')} />}
      {actor.isError && <Alert color="red">{errorMessage(actor.error)}</Alert>}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {data && (
        <>
          <Group justify="space-between" align="flex-start">
            <Title order={3}>{data.name}</Title>
            {canEdit && (
              <Group gap="xs">
                <Button variant="default" onClick={() => setEditing(true)}>
                  {t('app.edit')}
                </Button>
                <Button variant="subtle" color="red" onClick={() => void remove()}>
                  {t('app.delete')}
                </Button>
              </Group>
            )}
          </Group>
          <Paper withBorder p="md">
            <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
              <Field label={label('type')}>{data.actor_type?.name}</Field>
              <Field label={label('sector')}>{data.sector?.name}</Field>
              <Field label={label('cuit')}>{formatCuit(data.cuit)}</Field>
              <Field label={label('employees')}>{data.employee_count}</Field>
              <Field label={label('phone')}>{data.phone}</Field>
              <Field label={label('email')}>{data.email}</Field>
              <Field label={label('address')}>{data.address}</Field>
              <Field label={label('notes')}>{data.notes}</Field>
            </SimpleGrid>
          </Paper>

          <Stack gap="xs" component="section">
            <Group justify="space-between">
              <Title order={4}>{label('people')}</Title>
              {canEdit && !linking && (
                <Button variant="default" onClick={() => setLinking(true)}>
                  {label('linkPerson')}
                </Button>
              )}
            </Group>
            {linking && <LinkPersonPanel actor={data} onDone={() => setLinking(false)} />}
            {data.people.length === 0 && <Text c="dimmed">{label('noPeople')}</Text>}
            {data.people.map((link) => (
              <Group key={link.id} justify="space-between">
                <Group gap="xs">
                  <Anchor component={Link} to={`${BASE_PATH}/people/${link.person.id}`}>
                    {link.person.person.full_name}
                  </Anchor>
                  <Badge variant="light" color="gray">
                    {t(`economic.roles.${link.role}`)}
                  </Badge>
                </Group>
                {canEdit && (
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    color="red"
                    aria-label={label('unlinkNamed', { name: link.person.person.full_name })}
                    onClick={() =>
                      void action.run(() =>
                        send('DELETE', `/actors/${data.id}/people/${link.id}`),
                      )
                    }
                  >
                    {label('unlink')}
                  </Button>
                )}
              </Group>
            ))}
          </Stack>

          <AssignmentsPanel target={{ actor_id: data.id }} canEdit={canEdit} />

          <Modal opened={editing} onClose={() => setEditing(false)} title={label('editTitle')} size="lg">
            {editing && <ActorForm actor={data} onDone={() => setEditing(false)} />}
          </Modal>
        </>
      )}
    </Stack>
  )
}
