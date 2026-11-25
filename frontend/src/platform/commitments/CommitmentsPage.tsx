import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { errorMessage } from '../errorMessage'
import { formatDate } from '../format'
import { HelpTh } from '../HelpTh'
import { Pager } from '../Pager'
import { fitPage, usePaging } from '../paging'
import { SearchInput } from '../SearchInput'
import { SubjectLabel } from '../subjects/SubjectLabel'
import { PATH, send, useCommitments } from './api'
import { CommitmentForm } from './CommitmentForm'
import { Origin } from './Origin'
import { PostponedBadge } from './PostponedBadge'
import { StateBadge } from './StateBadge'
import { type Relation, RELATIONS, STATES } from './types'

function CommitmentsList({ relation }: { relation: Relation }) {
  const { t } = useTranslation()
  const [filters, setFilters] = useState({ q: '', state: 'pending' })
  const paging = usePaging(`commitments.${relation}`)
  const commitments = useCommitments({
    relation,
    ...filters,
    limit: paging.limit,
    offset: paging.offset,
  })
  fitPage(paging, commitments)
  const label = (key: string) => t(`commitments.list.${key}`)
  const help = (key: string) => t(`commitments.help.${key}`)
  const filter = (field: keyof typeof filters) => (value: string) => {
    setFilters((current) => ({ ...current, [field]: value }))
    // A different search starts again from its first page.
    paging.restart()
  }
  const rows = commitments.data?.items ?? []
  const mine = relation === 'mine'

  return (
    <Stack>
      <Group align="flex-end">
        <SearchInput value={filters.q} onChange={filter('q')} placeholder={label('searchHint')} />
        <NativeSelect
          label={label('state')}
          value={filters.state}
          onChange={(event) => filter('state')(event.currentTarget.value)}
          data={[
            { value: 'pending', label: label('pending') },
            ...STATES.map((value) => ({ value, label: t(`commitments.states.${value}`) })),
            { value: '', label: label('allStates') },
          ]}
        />
      </Group>
      {commitments.isLoading && <Loader aria-label={t('app.loading')} />}
      {commitments.isError && <Alert color="red">{errorMessage(commitments.error)}</Alert>}
      {commitments.data?.total === 0 && <Text c="dimmed">{label(`empty.${relation}`)}</Text>}
      {rows.length > 0 && (
        <Table.ScrollContainer minWidth={760}>
          <Table highlightOnHover aria-label={t(`commitments.relations.${relation}`)}>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('description')}>{label('description')}</HelpTh>
                {!mine && <HelpTh help={help('owner')}>{label('owner')}</HelpTh>}
                <HelpTh help={help('dueDate')}>{label('dueDate')}</HelpTh>
                <HelpTh help={help('state')}>{label('state')}</HelpTh>
                <HelpTh help={help('subject')}>{label('subject')}</HelpTh>
                <HelpTh help={help('origin')}>{label('origin')}</HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((commitment) => (
                <Table.Tr key={commitment.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`${PATH}/${commitment.id}`}>
                      {commitment.description}
                    </Anchor>
                  </Table.Td>
                  {!mine && <Table.Td>{commitment.owner.full_name}</Table.Td>}
                  <Table.Td>{formatDate(commitment.due_date)}</Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      <StateBadge state={commitment.state} />
                      <PostponedBadge times={commitment.times_postponed} />
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {commitment.subject ? (
                      <SubjectLabel subject={commitment.subject} />
                    ) : (
                      t('app.none')
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Origin commitment={commitment} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {commitments.data && <Pager {...paging.pager(commitments.data.total)} />}
    </Stack>
  )
}

/** Everyone's commitments: those they owe, gave to others or are attached to. */
export function CommitmentsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [creating, setCreating] = useState(false)
  const asked = params.get('list')
  const relation = RELATIONS.find((option) => option === asked) ?? 'mine'

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('commitments.section')}</Title>
        <Button onClick={() => setCreating(true)}>{t('commitments.create')}</Button>
      </Group>
      <Tabs
        value={relation}
        onChange={(value) => navigate(value === 'mine' ? PATH : `${PATH}?list=${value}`)}
      >
        <Tabs.List>
          {RELATIONS.map((key) => (
            <Tabs.Tab key={key} value={key}>
              {t(`commitments.relations.${key}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      {/* Each list keeps its own filters and page. */}
      <CommitmentsList key={relation} relation={relation} />
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title={t('commitments.create')}
        size="lg"
      >
        {creating && (
          <CommitmentForm
            save={(body) => send('POST', PATH, body)}
            onDone={() => setCreating(false)}
          />
        )}
      </Modal>
    </Stack>
  )
}
