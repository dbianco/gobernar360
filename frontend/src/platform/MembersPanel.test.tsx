import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { UsersAdminPage } from './UsersAdminPage'

function member(index: number) {
  return {
    membership_id: `ms-${index}`,
    user: { id: `u-${index}`, email: `u${index}@noetinger.test`, full_name: `Usuario ${index}` },
    is_admin: false,
    grants: {},
  }
}

function renderUsers(total = 25) {
  const requests = mockApi('get', '/admin/users', ({ url }) => {
    const limit = Number(url.searchParams.get('limit'))
    const offset = Number(url.searchParams.get('offset'))
    const items = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) =>
      member(offset + i + 1),
    )
    return { items, total }
  })
  mockApi('get', '/admin/dashboards', ['projects'])
  renderApp(<UsersAdminPage />, { me: makeMe({ isAdmin: true }) })
  return requests
}

const query = (request: { url: URL }) => [
  request.url.searchParams.get('limit'),
  request.url.searchParams.get('offset'),
]

it('lists ten users per page and moves between pages', async () => {
  const requests = renderUsers()
  const user = userEvent.setup()

  expect(await screen.findByText('Usuario 10')).toBeInTheDocument()
  expect(screen.queryByText('Usuario 11')).toBeNull()
  expect(screen.getByText(t('app.pager.range', { from: 1, to: 10, total: 25 }))).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))

  expect(await screen.findByText('Usuario 11')).toBeInTheDocument()
  expect(query(requests.at(-1)!)).toEqual(['10', '10'])
})

it('shows 20 or 50 per page when chosen, from the first page', async () => {
  const requests = renderUsers(60)
  const user = userEvent.setup()
  await screen.findByText('Usuario 1')
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))
  await screen.findByText('Usuario 11')

  await user.selectOptions(
    screen.getByRole('combobox', { name: t('app.pager.pageSize') }),
    t('app.pager.perPage', { count: 50 }),
  )

  expect(await screen.findByText('Usuario 50')).toBeInTheDocument()
  expect(query(requests.at(-1)!)).toEqual(['50', '0'])
  expect(screen.getByText(t('app.pager.range', { from: 1, to: 50, total: 60 }))).toBeInTheDocument()
})

it('hides the pager while everyone fits in the smallest page', async () => {
  renderUsers(3)

  await screen.findByText('Usuario 3')

  expect(screen.queryByRole('combobox', { name: t('app.pager.pageSize') })).toBeNull()
})

async function openImport() {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: t('users.import.open') }))
  const dialog = await screen.findByRole('dialog')
  return { user, dialog }
}

function chooseFile(dialog: HTMLElement, file: File, user: ReturnType<typeof userEvent.setup>) {
  const input = dialog.ownerDocument.querySelector<HTMLInputElement>('input[type="file"]')!
  return user.upload(input, file)
}

it('offers an example file to download', async () => {
  renderUsers(3)
  const { dialog } = await openImport()

  expect(
    within(dialog).getByRole('link', { name: t('users.import.downloadExample') }),
  ).toHaveAttribute('href', '/api/admin/users/import-template.csv')
})

it('imports a file and says what changed', async () => {
  const imported = mockApi('post', '/admin/users/import', { created: 2, updated: 1, unchanged: 0 })
  renderUsers(3)
  const { user, dialog } = await openImport()
  const content = 'email,nombre\nana@noetinger.test,Ana Pérez\n'

  await chooseFile(dialog, new File([content], 'usuarios.csv', { type: 'text/csv' }), user)
  await user.click(within(dialog).getByRole('button', { name: t('users.import.submit') }))

  expect(
    await screen.findByText(t('users.import.done', { created: 2, updated: 1, unchanged: 0 })),
  ).toBeInTheDocument()
  expect(imported[0].body).toEqual({ csv: content })
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('reads files saved by older Excel versions', async () => {
  const imported = mockApi('post', '/admin/users/import', { created: 1, updated: 0, unchanged: 0 })
  renderUsers(3)
  const { user, dialog } = await openImport()
  // "José" in Windows-1252: é is the single byte 0xE9, which is not valid UTF-8.
  const ascii = Array.from('email,nombre\nj@x.test,Jos', (char) => char.charCodeAt(0))
  const bytes = new Uint8Array([...ascii, 0xe9, 0x0a])

  await chooseFile(dialog, new File([bytes], 'u.csv'), user)
  await user.click(within(dialog).getByRole('button', { name: t('users.import.submit') }))

  await waitFor(() => expect(imported).toHaveLength(1))
  expect(imported[0].body).toEqual({ csv: 'email,nombre\nj@x.test,José\n' })
})

it('lists the problems of a file by line and says nothing changed', async () => {
  mockApi(
    'post',
    '/admin/users/import',
    {
      error: {
        code: 'invalid_csv',
        message: 'The file has errors.',
        details: [
          { line: 3, code: 'invalid_email', column: 'email', value: 'no-es-email' },
          { line: 5, code: 'invalid_level', column: 'Proyectos', value: 'Jefa' },
        ],
      },
    },
    422,
  )
  renderUsers(3)
  const { user, dialog } = await openImport()

  await chooseFile(dialog, new File(['x'], 'u.csv', { type: 'text/csv' }), user)
  await user.click(within(dialog).getByRole('button', { name: t('users.import.submit') }))

  expect(
    await within(dialog).findByText(t('users.import.hasErrors', { count: 2 })),
  ).toBeInTheDocument()
  const rows = within(dialog).getAllByRole('row').slice(1)
  expect(rows.map((row) => row.textContent)).toEqual([
    `3${t('users.import.errors.invalid_email', { value: 'no-es-email' })}`,
    `5${t('users.import.errors.invalid_level', { column: 'Proyectos', value: 'Jefa' })}`,
  ])
  expect(within(dialog).getByText(t('users.import.nothingChanged'))).toBeInTheDocument()
})

it('says when the file cannot be read, without calling the server', async () => {
  const imported = mockApi('post', '/admin/users/import', { created: 0, updated: 0, unchanged: 0 })
  renderUsers(3)
  const { user, dialog } = await openImport()
  const read = vi
    .spyOn(FileReader.prototype, 'readAsArrayBuffer')
    .mockImplementation(function (this: FileReader) {
      this.onerror?.(new ProgressEvent('error') as ProgressEvent<FileReader>)
    })

  await chooseFile(dialog, new File(['x'], 'u.csv', { type: 'text/csv' }), user)
  await user.click(within(dialog).getByRole('button', { name: t('users.import.submit') }))

  expect(await within(dialog).findByText(t('users.import.unreadable'))).toBeInTheDocument()
  expect(imported).toHaveLength(0)
  read.mockRestore()
})

it('describes a problem it has no words for in general terms', async () => {
  mockApi(
    'post',
    '/admin/users/import',
    {
      error: {
        code: 'invalid_csv',
        message: 'The file has errors.',
        details: [{ line: 2, code: 'something_new', column: 'email', value: 'x' }],
      },
    },
    422,
  )
  renderUsers(3)
  const { user, dialog } = await openImport()

  await chooseFile(dialog, new File(['x'], 'u.csv', { type: 'text/csv' }), user)
  await user.click(within(dialog).getByRole('button', { name: t('users.import.submit') }))

  const rows = await within(dialog).findAllByRole('row')
  expect(rows[1]).toHaveTextContent(`2${t('users.import.errors.generic')}`)
})

it('says the file has errors even when the server does not say which', async () => {
  mockApiError('post', '/admin/users/import', 422, 'invalid_csv')
  renderUsers(3)
  const { user, dialog } = await openImport()

  // Nothing to send until a file is chosen.
  expect(within(dialog).getByRole('button', { name: t('users.import.submit') })).toBeDisabled()
  await chooseFile(dialog, new File(['x'], 'u.csv', { type: 'text/csv' }), user)
  await user.click(within(dialog).getByRole('button', { name: t('users.import.submit') }))

  await waitFor(() =>
    expect(within(dialog).getByRole('button', { name: t('users.import.submit') })).toBeEnabled(),
  )
  expect(within(dialog).queryByRole('row')).toBeNull()
})
