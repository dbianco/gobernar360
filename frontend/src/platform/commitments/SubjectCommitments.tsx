import { Alert, Paper, Stack, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../errorMessage'
import type { SubjectRef } from '../subjects/types'
import { useSubjectCommitments } from './api'
import { CommitmentLines } from './CommitmentLines'

/**
 * The open commitments about a record, for its own page. Nothing is shown when there are
 * none, or when whoever is signed in has no access to the dashboard that keeps them.
 */
export function SubjectCommitments({ subject }: { subject: SubjectRef }) {
  const { t } = useTranslation()
  const commitments = useSubjectCommitments(subject)

  if (commitments.isError) return <Alert color="red">{errorMessage(commitments.error)}</Alert>
  if (!commitments.data?.length) return null
  return (
    <Paper withBorder p="md" component="section" aria-label={t('commitments.title')}>
      <Stack gap="xs">
        <Title order={4}>{t('commitments.title')}</Title>
        <CommitmentLines commitments={commitments.data} />
      </Stack>
    </Paper>
  )
}
