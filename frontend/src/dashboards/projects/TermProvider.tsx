import { Alert, Anchor, Center, Loader, NativeSelect, Stack, Text, Title } from '@mantine/core'
import { type ReactNode, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { hasLevel } from '../../platform/types'
import { useTerms } from './api'
import { latestTerm, TermContext, useTerm } from './termContext'

const STORAGE_KEY = 'g360.projects.term'

// Remembering the chosen term is a convenience; the app must work without storage.
function readStoredTermId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function storeTermId(termId: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, termId)
  } catch {
    // Ignored on purpose: see above.
  }
}

/** Provides the selected term to the projects screens, or explains that none exists yet. */
export function TermProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const terms = useTerms()
  const [chosenId, setChosenId] = useState<string | null>(readStoredTermId)

  const state = useMemo(() => {
    const list = terms.data ?? []
    const term = list.find((candidate) => candidate.id === chosenId) ?? latestTerm(list)
    if (!term) return null
    return {
      term,
      terms: list,
      setTermId: (termId: string) => {
        storeTermId(termId)
        setChosenId(termId)
      },
    }
  }, [terms.data, chosenId])

  if (terms.isLoading) {
    return (
      <Center mih={200}>
        <Loader aria-label={t('app.loading')} />
      </Center>
    )
  }
  if (terms.isError) return <Alert color="red">{errorMessage(terms.error)}</Alert>
  if (!state) {
    const canManage = hasLevel(me, 'projects', 'admin')
    return (
      <Stack align="center" mt="xl" gap="xs">
        <Title order={3}>{t('projects.term.emptyTitle')}</Title>
        <Text c="dimmed">
          {t(canManage ? 'projects.term.emptyBody' : 'projects.term.emptyViewerBody')}
        </Text>
        {canManage && (
          <Anchor component={Link} to="/d/projects/parameters">
            {t('projects.term.goToParameters')}
          </Anchor>
        )}
      </Stack>
    )
  }
  return <TermContext.Provider value={state}>{children}</TermContext.Provider>
}

/** "Cambiar gestión": switches the term being viewed. Hidden when there is only one. */
export function TermSelect() {
  const { t } = useTranslation()
  const { term, terms, setTermId } = useTerm()
  if (terms.length < 2) return <Text c="dimmed">{term.name}</Text>
  return (
    <NativeSelect
      aria-label={t('projects.term.change')}
      value={term.id}
      onChange={(event) => setTermId(event.currentTarget.value)}
      data={terms.map((candidate) => ({ value: candidate.id, label: candidate.name }))}
    />
  )
}
