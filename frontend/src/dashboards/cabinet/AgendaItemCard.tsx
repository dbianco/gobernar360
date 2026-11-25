import { Badge, Button, Checkbox, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { CommitmentLine } from './CommitmentLine'
import { MoveButtons } from './MoveButtons'
import { SavedTextarea } from './SavedTextarea'
import type { AgendaItem, Commitment } from './types'

export interface ItemActions {
  move: (by: -1 | 1) => void
  saveNotes: (notes: string) => void
  setDiscussed: (discussed: boolean) => void
  edit: () => void
  remove: () => void
  addCommitment: () => void
  editCommitment: (commitment: Commitment) => void
  removeCommitment: (commitment: Commitment) => void
}

/** One point of a meeting: what it is about, what was said and what was agreed. */
export function AgendaItemCard(props: {
  item: AgendaItem
  number: number
  last: boolean
  /** None when the meeting is closed or whoever reads it only reads. */
  actions: ItemActions | null
}) {
  const { t } = useTranslation()
  const { item, actions } = props
  const label = (key: string, options = {}) => t(`cabinet.agenda.${key}`, options)
  const named = { name: item.title }

  return (
    <Paper withBorder p="md" component="section" aria-label={item.title}>
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Stack gap={4} miw={0}>
            <Title order={5}>{`${props.number}. ${item.title}`}</Title>
            {item.subject && (
              <SubjectLabel subject={item.subject} stateOnly={item.source === 'light'} />
            )}
          </Stack>
          <Group gap="xs" wrap="nowrap">
            {item.carried && (
              <Badge variant="light" color="orange" tt="none">
                {label('carried')}
              </Badge>
            )}
            {!actions && !item.discussed && (
              <Badge variant="light" color="gray" tt="none">
                {label('notDiscussed')}
              </Badge>
            )}
            {actions && (
              <MoveButtons
                name={item.title}
                first={props.number === 1}
                last={props.last}
                onMove={actions.move}
              />
            )}
          </Group>
        </Group>
        {item.topic && <CommitmentLine commitment={item.topic} hideName />}
        {actions ? (
          <>
            <SavedTextarea
              label={label('notes')}
              aria-label={label('notesOf', named)}
              autosize
              minRows={2}
              maxLength={10000}
              saved={item.notes}
              onSave={actions.saveNotes}
            />
            <Checkbox
              label={label('discussed')}
              aria-label={label('discussedNamed', named)}
              checked={item.discussed}
              onChange={(event) => actions.setDiscussed(event.currentTarget.checked)}
            />
          </>
        ) : (
          item.notes && <Text style={{ whiteSpace: 'pre-wrap' }}>{item.notes}</Text>
        )}
        {item.commitments.length > 0 && (
          <Stack gap="xs">
            <Text fw={600} size="sm">
              {label('agreed')}
            </Text>
            {item.commitments.map((commitment) => (
              <CommitmentLine
                key={commitment.id}
                commitment={commitment}
                onEdit={actions ? () => actions.editCommitment(commitment) : undefined}
                onRemove={actions ? () => actions.removeCommitment(commitment) : undefined}
              />
            ))}
          </Stack>
        )}
        {actions && (
          <Group gap="xs">
            <Button
              size="xs"
              aria-label={label('addCommitmentTo', named)}
              onClick={actions.addCommitment}
            >
              {label('addCommitment')}
            </Button>
            {item.source === 'manual' && (
              <Button
                size="xs"
                variant="default"
                aria-label={label('editNamed', named)}
                onClick={actions.edit}
              >
                {t('app.edit')}
              </Button>
            )}
            {item.commitments.length === 0 && (
              <Button
                size="xs"
                variant="subtle"
                color="red"
                aria-label={label('removeNamed', named)}
                onClick={actions.remove}
              >
                {label('remove')}
              </Button>
            )}
          </Group>
        )}
      </Stack>
    </Paper>
  )
}
