import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { SubjectLabel } from './SubjectLabel'
import { refOf, type Subject } from './types'

const PROJECT: Subject = {
  access: 'visible',
  kind: 'project',
  dashboard_key: 'projects',
  ref: 'pr-1',
  label: 'Plaza central',
  path: '/d/projects/projects/pr-1',
  color: null,
}
const MONTH: Subject = {
  access: 'visible',
  kind: 'month',
  dashboard_key: 'environment',
  ref: '2026-10',
  label: 'Ambiental, octubre de 2026',
  path: '/d/environment',
  color: 'red',
}
const hidden = (subject: Subject, access: 'restricted' | 'deleted' = 'restricted'): Subject => ({
  ...subject,
  access,
  dashboard_key: subject.kind === 'month' ? null : subject.dashboard_key,
  ref: null,
  label: null,
  path: null,
  color: null,
})
const show = (subject: Subject, stateOnly = false) =>
  renderApp(<SubjectLabel subject={subject} stateOnly={stateOnly} />, { me: makeMe() })

it('names a record and leads to it', async () => {
  show(PROJECT)

  expect(await screen.findByRole('link', { name: 'Plaza central' })).toHaveAttribute(
    'href',
    '/d/projects/projects/pr-1',
  )
})

it('says the state of a month besides showing its color', async () => {
  show(MONTH)

  const link = await screen.findByRole('link', {
    name: `Ambiental, octubre de 2026 (${t('status.states.red')})`,
  })
  expect(link).toHaveAttribute('href', '/d/environment')
})

it('says a project the reader cannot open is linked, and nothing about it', async () => {
  show(hidden(PROJECT))

  expect(await screen.findByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  expect(screen.queryByRole('link')).toBeNull()
})

it('has a text for kinds it does not know and for months', async () => {
  const view = show(hidden({ ...PROJECT, dashboard_key: 'complaints', kind: 'complaint' }))
  expect(await screen.findByText(t('subjects.restricted.record'))).toBeInTheDocument()
  view.unmount()

  show(hidden(MONTH))
  expect(await screen.findByText(t('subjects.restricted.month'))).toBeInTheDocument()
})

it('says when what was linked no longer exists', async () => {
  const view = show(hidden(PROJECT, 'deleted'))
  expect(await screen.findByText(t('subjects.deleted.projects.project'))).toBeInTheDocument()
  view.unmount()

  show(hidden({ ...PROJECT, kind: 'other' }, 'deleted'))
  expect(await screen.findByText(t('subjects.deleted.record'))).toBeInTheDocument()
})

it('shows only the state next to a title that already names the month', async () => {
  const lit = show(MONTH, true)
  expect(await screen.findByRole('link', { name: t('status.states.red') })).toBeInTheDocument()
  expect(screen.queryByText(/octubre/)).toBeNull()
  lit.unmount()

  const unlit = show({ ...MONTH, color: null }, true)
  expect(await screen.findByRole('link', { name: t('status.states.none') })).toBeInTheDocument()
  unlit.unmount()

  show(hidden(MONTH), true)
  expect(screen.queryByText(t('subjects.restricted.month'))).toBeNull()
})

it('gives a reference only for what can be linked again', () => {
  expect(refOf(PROJECT)).toEqual({ dashboard_key: 'projects', kind: 'project', ref: 'pr-1' })
  expect(refOf(hidden(PROJECT))).toBeNull()
  expect(refOf(hidden(PROJECT, 'deleted'))).toBeNull()
  expect(refOf(null)).toBeNull()
  expect(refOf(undefined)).toBeNull()
})
