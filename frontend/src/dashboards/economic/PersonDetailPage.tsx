import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate } from '../../platform/format'
import { hasLevel } from '../../platform/access'
import { BASE_PATH, send, useAction, usePerson } from './api'
import { AssignmentsPanel } from './AssignmentsPanel'
import { Field } from '../../platform/Field'
import { formatDni } from '../../platform/format'
import { formatCuil } from '../../platform/people/documents'
import { PersonForm } from './PersonForm'
import { useConfirm } from '../../platform/confirmContext'

/** Everything the dashboard knows about one person, and the tools they received. */
export function PersonDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const { me } = useAuth()
  const navigate = useNavigate()
  const person = usePerson(id)
  const action = useAction()
  const [editing, setEditing] = useState(false)
  const canEdit = hasLevel(me, 'economic', 'editor')
  const listPath = `${BASE_PATH}/people`
  const data = person.data
  const label = (key: string, options = {}) => t(`economic.people.${key}`, options)
  const confirm = useConfirm()
  const askDelete = (message: string) =>
    confirm({ message, confirmLabel: t('app.delete'), danger: true })

  async function remove(shown: NonNullable<typeof person.data>) {
    if (!(await askDelete(label('deleteConfirm', { name: shown.person.full_name })))) return
    const deleted = await action.run(async () => {
      await send('DELETE', `/people/${shown.id}`)
      return true
    })
    if (deleted) navigate(listPath)
  }

  return (
    <Stack>
      <Anchor component={Link} to={listPath}>
        {label('back')}
      </Anchor>
      {person.isLoading && <Loader aria-label={t('app.loading')} />}
      {person.isError && <Alert color="red">{errorMessage(person.error)}</Alert>}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {data && (
        <>
          <Group justify="space-between" align="flex-start">
            <Title order={3}>{data.person.full_name}</Title>
            {canEdit && (
              <Group gap="xs">
                <Button variant="default" onClick={() => setEditing(true)}>
                  {t('app.edit')}
                </Button>
                <Button variant="subtle" color="red" onClick={() => void remove(data)}>
                  {label('remove')}
                </Button>
              </Group>
            )}
          </Group>
          <Paper withBorder p="md">
            <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
              <Field label={t('people.dni')}>{formatDni(data.person.dni)}</Field>
              <Field label={t('people.cuil')}>{formatCuil(data.person.cuil)}</Field>
              <Field label={t('people.birthDate')}>{formatDate(data.person.birth_date)}</Field>
              <Field label={t('people.phone')}>{data.person.phone}</Field>
              <Field label={t('people.email')}>{data.person.email}</Field>
              <Field label={t('people.address')}>{data.person.address}</Field>
              <Field label={t('people.neighborhood')}>{data.person.neighborhood}</Field>
              <Field label={label('employmentStatus')}>
                {t(`economic.employmentStatuses.${data.employment_status}`)}
              </Field>
              <Field label={label('occupation')}>{data.occupation}</Field>
            </SimpleGrid>
          </Paper>

          <Stack gap="xs" component="section">
            <Title order={4}>{label('actors')}</Title>
            {data.actors.length === 0 && <Text c="dimmed">{label('noActors')}</Text>}
            {data.actors.map((link) => (
              <Group key={link.id} gap="xs">
                <Anchor component={Link} to={`${BASE_PATH}/actors/${link.actor.id}`}>
                  {link.actor.name}
                </Anchor>
                <Badge variant="light" color="gray">
                  {t(`economic.roles.${link.role}`)}
                </Badge>
              </Group>
            ))}
          </Stack>

          <AssignmentsPanel target={{ person_id: data.id }} canEdit={canEdit} />

          <Modal opened={editing} onClose={() => setEditing(false)} title={label('editTitle')} size="lg">
            {editing && <PersonForm person={data} onDone={() => setEditing(false)} />}
          </Modal>
        </>
      )}
    </Stack>
  )
}
