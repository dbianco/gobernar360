import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Field } from '../../platform/Field'
import { formatDni } from '../../platform/format'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, send, useAction, useHousehold } from './api'
import { HouseholdForm } from './HouseholdForm'
import { PersonSearch } from './PersonSearch'
import { RecordsPanel } from './RecordsPanel'
import { type HouseholdDetail, type Relationship, RELATIONSHIPS } from './types'
import { useConfirm } from '../../platform/confirmContext'

function useRelationshipOptions() {
  const { t } = useTranslation()
  return RELATIONSHIPS.map((value) => ({ value, label: t(`social.relationships.${value}`) }))
}

/** Find a person of the dashboard and add them to the household. */
function AddMemberPanel(props: {
  household: HouseholdDetail
  run: (personId: string, relationship: Relationship) => Promise<unknown>
  pending: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const options = useRelationshipOptions()
  // What the member picked for the next addition; until they pick, a household
  // starts with its head and after that most additions are children.
  const [chosen, setChosen] = useState<Relationship | null>(null)
  const relationship = chosen ?? (props.household.head ? 'child' : 'head')
  const label = (key: string, options = {}) => t(`social.households.${key}`, options)
  const members = new Set(props.household.members.map((member) => member.id))

  return (
    <Paper withBorder p="md">
      <PersonSearch
        hide={(person) => members.has(person.id)}
        extra={
          <>
            <NativeSelect
              label={label('relationship')}
              value={relationship}
              onChange={(event) => setChosen(event.currentTarget.value as Relationship)}
              data={options}
            />
            <Button variant="default" onClick={props.onClose}>
              {t('app.cancel')}
            </Button>
          </>
        }
      >
        {(person) =>
          person.household ? (
            <Text size="sm" c="dimmed">
              {label('inAnother', { name: person.household.name })}
            </Text>
          ) : (
            <Button
              size="compact-sm"
              aria-label={label('addNamed', { name: person.person.full_name })}
              loading={props.pending}
              onClick={() =>
                // The choice was for this person: the next one starts from the default again.
                void props.run(person.id, relationship).then((saved) => saved && setChosen(null))
              }
            >
              {label('add')}
            </Button>
          )
        }
      </PersonSearch>
    </Paper>
  )
}

/** One household: where it lives, who belongs to it and everything done with them. */
export function HouseholdDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const { me } = useAuth()
  const navigate = useNavigate()
  const household = useHousehold(id)
  const action = useAction()
  const options = useRelationshipOptions()
  const [editing, setEditing] = useState(false)
  const [adding, setAdding] = useState(false)
  const canEdit = hasLevel(me, 'social', 'editor')
  const listPath = `${BASE_PATH}/households`
  const data = household.data
  const label = (key: string, options = {}) => t(`social.households.${key}`, options)
  const confirm = useConfirm()
  const askDelete = (message: string) =>
    confirm({ message, confirmLabel: t('app.delete'), danger: true })
  const memberPath = (personId: string) => `/households/${id}/members/${personId}`

  const setMember = (personId: string, relationship: Relationship) =>
    action.run(() => send('PUT', memberPath(personId), { relationship }))

  async function remove(shown: NonNullable<typeof household.data>) {
    if (!(await askDelete(label('deleteConfirm', { name: shown.name })))) return
    const deleted = await action.run(async () => {
      await send('DELETE', `/households/${shown.id}`)
      return true
    })
    if (deleted) navigate(listPath)
  }

  return (
    <Stack>
      <Anchor component={Link} to={listPath}>
        {label('back')}
      </Anchor>
      {household.isLoading && <Loader aria-label={t('app.loading')} />}
      {household.isError && <Alert color="red">{errorMessage(household.error)}</Alert>}
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
                <Button variant="subtle" color="red" onClick={() => void remove(data)}>
                  {t('app.delete')}
                </Button>
              </Group>
            )}
          </Group>
          <Paper withBorder p="md">
            <SimpleGrid cols={{ base: 1, xs: 2 }}>
              <Field label={label('address')}>{data.address}</Field>
              <Field label={label('neighborhood')}>{data.neighborhood}</Field>
            </SimpleGrid>
          </Paper>

          <Stack gap="xs" component="section">
            <Group justify="space-between">
              <Title order={4}>{label('members')}</Title>
              {canEdit && !adding && (
                <Button onClick={() => setAdding(true)}>{label('addMember')}</Button>
              )}
            </Group>
            {adding && (
              <AddMemberPanel
                household={data}
                run={setMember}
                pending={action.pending}
                onClose={() => setAdding(false)}
              />
            )}
            {data.members.length === 0 && <Text c="dimmed">{label('noMembers')}</Text>}
            {data.members.length > 0 && (
              <Table.ScrollContainer minWidth={480}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <HelpTh help={t('social.help.householdDetailPage.fullName')}>
                        {t('people.fullName')}
                      </HelpTh>
                      <HelpTh help={t('social.help.householdDetailPage.dni')}>
                        {t('people.dni')}
                      </HelpTh>
                      <HelpTh help={t('social.help.householdDetailPage.relationship')}>
                        {label('relationship')}
                      </HelpTh>
                      <Table.Th />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {data.members.map((member) => (
                      <Table.Tr key={member.id}>
                        <Table.Td>
                          <Anchor component={Link} to={`${BASE_PATH}/people/${member.id}`}>
                            {member.full_name}
                          </Anchor>
                        </Table.Td>
                        <Table.Td>{formatDni(member.dni)}</Table.Td>
                        <Table.Td>
                          {canEdit ? (
                            <NativeSelect
                              aria-label={label('relationshipOf', { name: member.full_name })}
                              size="xs"
                              value={member.relationship}
                              onChange={(event) =>
                                void setMember(member.id, event.currentTarget.value as Relationship)
                              }
                              data={options}
                            />
                          ) : (
                            t(`social.relationships.${member.relationship}`)
                          )}
                        </Table.Td>
                        <Table.Td ta="right">
                          {canEdit && (
                            <Button
                              size="compact-xs"
                              variant="subtle"
                              color="red"
                              aria-label={label('removeNamed', { name: member.full_name })}
                              onClick={() =>
                                void action.run(() => send('DELETE', memberPath(member.id)))
                              }
                            >
                              {label('remove')}
                            </Button>
                          )}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
          </Stack>

          <RecordsPanel scope={{ household_id: data.id }} canEdit={canEdit} />

          <Modal opened={editing} onClose={() => setEditing(false)} title={label('editTitle')}>
            {editing && <HouseholdForm household={data} onDone={() => setEditing(false)} />}
          </Modal>
        </>
      )}
    </Stack>
  )
}
