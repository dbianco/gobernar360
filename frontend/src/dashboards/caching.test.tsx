import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { type ReactNode, useState } from 'react'
import { expect, it } from 'vitest'

import { useMunicipalities, useRegisteredDashboards } from '../platform/operatorApi'
import { OWN_MUNICIPALITY, SettingsScopeContext, useSettingsScope } from '../platform/settings/scope'
import { useDashboardStatus, useSetStatus } from '../platform/status/api'
import { mockApi, type RecordedRequest } from '../test/server'
import * as economic from './economic/api'
import * as environment from './environment/api'
import * as procedures from './procedures/api'
import * as projects from './projects/api'
import * as social from './social/api'

// What is asked again after a change, and what is not: a screen that does not refresh shows
// what no longer is, and two questions that share a place in the cache show each other's answer.

const DASHBOARDS = {
  projects: { use: projects.useTerms, other: projects.useDepartments, path: '/terms', otherPath: '/departments', useAction: projects.useAction },
  environment: { use: environment.useSubcategories, other: environment.useVariables, path: '/subcategories', otherPath: '/variables', useAction: environment.useAction },
  economic: { use: economic.useSectors, other: economic.useActorTypes, path: '/sectors', otherPath: '/actor-types', useAction: economic.useAction },
  social: { use: social.useBenefits, other: social.useInterventionTypes, path: '/benefits', otherPath: '/intervention-types', useAction: social.useAction },
  procedures: { use: procedures.useAreas, other: procedures.useSources, path: '/areas', otherPath: '/sources', useAction: procedures.useAction },
} as const
type Key = keyof typeof DASHBOARDS
const KEYS = Object.keys(DASHBOARDS) as Key[]

function inCache(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
  return client
}

function Reads({ use, name }: { use: () => { data?: unknown }; name: string }) {
  return <p>{`${name}: ${JSON.stringify(use().data ?? null)}`}</p>
}

function Changes({ useAction }: { useAction: () => { run: (action: () => Promise<unknown>) => unknown } }) {
  const action = useAction()
  return <button onClick={() => void action.run(async () => true)}>change</button>
}

const asked = (requests: Record<string, RecordedRequest[]>) =>
  Object.fromEntries(Object.entries(requests).map(([key, list]) => [key, list.length]))

it.each(KEYS)('a change in %s refreshes its screens and the overview, and no other dashboard', async (changed) => {
  const requests = Object.fromEntries(
    KEYS.map((key) => [key, mockApi('get', `/dashboards/${key}${DASHBOARDS[key].path}`, [{ id: key }])]),
  )
  const client = inCache(
    <>
      {KEYS.map((key) => (
        <Reads key={key} use={DASHBOARDS[key].use} name={key} />
      ))}
      <Changes useAction={DASHBOARDS[changed].useAction} />
    </>,
  )
  // Every dashboard has its own answer, though they are kept in one place.
  for (const key of KEYS) {
    expect(await screen.findByText(`${key}: [{"id":"${key}"}]`)).toBeInTheDocument()
  }
  client.setQueryData(['overview'], [])
  client.setQueryData(['zones'], [])

  await userEvent.setup().click(screen.getByRole('button', { name: 'change' }))

  await waitFor(() => expect(requests[changed]).toHaveLength(2))
  expect(asked(requests)).toEqual(
    Object.fromEntries(KEYS.map((key) => [key, key === changed ? 2 : 1])),
  )
  expect(client.getQueryState(['overview'])?.isInvalidated).toBe(true)
  expect(client.getQueryState(['zones'])?.isInvalidated).toBe(false)
})

it.each(KEYS)('lists of %s do not take the place of each other', async (key) => {
  const { use, other, path, otherPath } = DASHBOARDS[key]
  mockApi('get', `/dashboards/${key}${path}`, [{ id: 'one' }])
  mockApi('get', `/dashboards/${key}${otherPath}`, [{ id: 'two' }])
  inCache(
    <>
      <Reads use={use} name="first" />
      <Reads use={other} name="second" />
    </>,
  )

  expect(await screen.findByText('first: [{"id":"one"}]')).toBeInTheDocument()
  expect(await screen.findByText('second: [{"id":"two"}]')).toBeInTheDocument()
})

it('keeps the rows on screen while the next search loads', async () => {
  const requests = mockApi('get', '/dashboards/economic/actors', (request) => {
    const q = request.url.searchParams.get('q')
    return { items: [{ id: q }], total: 1 } as never
  })
  function Search() {
    const [q, setQ] = useState('a')
    const actors = economic.useActors({ q })
    return (
      <>
        <p>{`rows: ${actors.data?.items.map((actor) => actor.id).join()}`}</p>
        <button onClick={() => setQ('b')}>next</button>
      </>
    )
  }
  inCache(<Search />)
  expect(await screen.findByText('rows: a')).toBeInTheDocument()
  const seen: string[] = []
  const watch = new MutationObserver(() => seen.push(screen.getByText(/^rows/).textContent ?? ''))
  watch.observe(document.body, { subtree: true, childList: true, characterData: true })

  await userEvent.setup().click(screen.getByRole('button', { name: 'next' }))
  expect(await screen.findByText('rows: b')).toBeInTheDocument()

  watch.disconnect()
  expect(seen).not.toContain('rows: undefined')
  expect(requests).toHaveLength(2)
})

it('asks for the requirements that match a search, and for all of them without one', async () => {
  const requests = mockApi('get', '/dashboards/procedures/requirements', [])
  inCache(
    <>
      <Reads use={() => procedures.useRequirements()} name="all" />
      <Reads use={() => procedures.useRequirements('dni')} name="some" />
    </>,
  )

  await waitFor(() => expect(requests).toHaveLength(2))
  expect(requests.map((request) => request.url.searchParams.get('q')).sort()).toEqual(['dni', null])
})

it('a status light refreshes the strips and the overview', async () => {
  const strip = mockApi('get', '/dashboards/projects/status', [])
  mockApi('get', '/dashboards/social/status', [{ month: 1, color: 'red' }])
  mockApi('put', '/dashboards/projects/status/2026/3', null, 204)
  function Light() {
    const { set } = useSetStatus('projects')
    return <button onClick={() => void set(2026, 3, 'green')}>set</button>
  }
  const client = inCache(
    <>
      <Reads use={() => useDashboardStatus('projects', 2026)} name="projects" />
      <Reads use={() => useDashboardStatus('social', 2026)} name="social" />
      <Light />
    </>,
  )
  expect(await screen.findByText('projects: []')).toBeInTheDocument()
  expect(await screen.findByText('social: [{"month":1,"color":"red"}]')).toBeInTheDocument()
  client.setQueryData(['overview'], [])
  client.setQueryData(['projects'], [])

  await userEvent.setup().click(screen.getByRole('button', { name: 'set' }))

  await waitFor(() => expect(strip).toHaveLength(2))
  expect(client.getQueryState(['overview'])?.isInvalidated).toBe(true)
  expect(client.getQueryState(['projects'])?.isInvalidated).toBe(false)
})

it('keeps the municipalities and the dashboards of the platform apart', async () => {
  mockApi('get', '/platform/municipalities', [{ id: 'm' }])
  mockApi('get', '/platform/dashboards', ['projects'])
  const client = inCache(
    <>
      <Reads use={useMunicipalities} name="municipalities" />
      <Reads use={useRegisteredDashboards} name="dashboards" />
    </>,
  )

  expect(await screen.findByText('municipalities: [{"id":"m"}]')).toBeInTheDocument()
  expect(await screen.findByText('dashboards: ["projects"]')).toBeInTheDocument()
  // Changes made by the operator refresh them by these names (see the pages under platform/).
  expect(client.getQueryData(['platform', 'municipalities'])).toEqual([{ id: 'm' }])
  expect(client.getQueryData(['platform', 'dashboards'])).toEqual(['projects'])
})

it("keeps each municipality's configuration, and each part of it, apart", () => {
  const scopes: ReturnType<typeof useSettingsScope>[] = []
  function Reader() {
    scopes.push(useSettingsScope())
    return null
  }
  render(
    <>
      <Reader />
      <SettingsScopeContext.Provider
        value={{ base: '/x/1', path: '/p/1', key: ['platform', 'municipalities', '1'], own: false }}
      >
        <Reader />
      </SettingsScopeContext.Provider>
    </>,
  )

  expect(scopes).toEqual([
    {
      base: '/admin',
      own: true,
      path: '/admin/settings',
      settingsKey: ['admin', 'settings'],
      templatesKey: ['admin', 'email-templates'],
      noticesKey: ['admin', 'settings-notices'],
    },
    {
      base: '/x/1',
      own: false,
      path: '/p/1',
      settingsKey: ['platform', 'municipalities', '1', 'settings'],
      templatesKey: ['platform', 'municipalities', '1', 'email-templates'],
      noticesKey: ['platform', 'municipalities', '1', 'settings-notices'],
    },
  ])
  expect(OWN_MUNICIPALITY.key).toEqual(['admin'])
})
