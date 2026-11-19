import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  Paper,
  SimpleGrid,
  Stack,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Field } from '../../platform/Field'
import { formatDate, formatDni } from '../../platform/format'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, send, useAction, usePerson } from './api'
import { PersonForm } from './PersonForm'
import { RecordsPanel } from './RecordsPanel'

/** One person: their data, their household and everything done with them. */
export function PersonDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const { me } = useAuth()
  const navigate = useNavigate()
  const person = usePerson(id)
  const action = useAction()
  const [editing, setEditing] = useState(false)
  const canEdit = hasLevel(me, 'social', 'editor')
  const listPath = `${BASE_PATH}/people`
  const data = person.data
  const label = (key: string, options = {}) => t(`social.people.${key}`, options)

  async function remove() {
    if (!data) return
    if (!window.confirm(label('deleteConfirm', { name: data.person.full_name }))) return
    const deleted = await action.run(async () => {
      await send('DELETE', `/people/${data.id}`)
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
                <Button variant="subtle" color="red" onClick={() => void remove()}>
                  {label('remove')}
                </Button>
              </Group>
            )}
          </Group>
          <Paper withBorder p="md">
            <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
              <Field label={t('people.dni')}>{formatDni(data.person.dni)}</Field>
              <Field label={t('people.birthDate')}>{formatDate(data.person.birth_date)}</Field>
              <Field label={t('people.phone')}>{data.person.phone}</Field>
              <Field label={t('people.email')}>{data.person.email}</Field>
              <Field label={t('people.address')}>{data.person.address}</Field>
              <Field label={t('people.neighborhood')}>{data.person.neighborhood}</Field>
              <Field label={label('household')}>
                {data.household ? (
                  <Anchor component={Link} to={`${BASE_PATH}/households/${data.household.id}`}>
                    {data.household.name}
                  </Anchor>
                ) : (
                  label('noHousehold')
                )}
              </Field>
              <Field label={label('relationship')}>
                {data.relationship && t(`social.relationships.${data.relationship}`)}
              </Field>
            </SimpleGrid>
          </Paper>

          <RecordsPanel scope={{ person_id: data.id }} canEdit={canEdit} />

          <Modal
            opened={editing}
            onClose={() => setEditing(false)}
            title={label('editTitle')}
            size="lg"
          >
            {editing && <PersonForm person={data} onDone={() => setEditing(false)} />}
          </Modal>
        </>
      )}
    </Stack>
  )
}
