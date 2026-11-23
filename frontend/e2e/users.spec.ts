import { expect, test } from '@playwright/test'

import { login, sidebar } from './helpers.ts'

// The users of a municipality: page by page, and imported from a CSV file.

function csvFile(name: string, rows: string[]) {
  return { name, mimeType: 'text/csv', buffer: Buffer.from(rows.join('\n') + '\n', 'utf-8') }
}

test('an administrator imports users from a CSV file and pages through them', async ({ page }) => {
  test.slow()
  const run = Date.now()
  const email = (n: number) => `csv-${run}-${n}@noetinger.test`
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()

  await page.getByRole('button', { name: 'Importar CSV' }).click()
  const dialog = page.getByRole('dialog')
  // The example is the header and two people, for the dashboards this municipality has.
  const example = await page.request.get('/api/admin/users/import-template.csv')
  const exampleRows = (await example.text()).replace('\ufeff', '').trim().split(/\r?\n/)
  expect(exampleRows[0]).toBe(
    'email,nombre,administrador,Económico,Ambiental,Trámites,Proyectos,Social',
  )
  expect(exampleRows).toHaveLength(3)
  await expect(dialog.getByRole('link', { name: 'Descargar un ejemplo' })).toBeVisible()

  const rows = ['email;nombre;administrador;Proyectos']
  for (let n = 1; n <= 12; n++) rows.push(`${email(n)};Importada ${run} ${n};no;Lectura`)
  // The same person again: the last row wins.
  rows.push(`${email(1)};Importada ${run} 1;no;Carga`)
  await dialog.locator('input[type="file"]').setInputFiles(csvFile('usuarios.csv', rows))
  await dialog.getByRole('button', { name: 'Importar' }).click()
  await expect(
    page.getByText(/Importación terminada: 12 usuarios agregados, 0 actualizados/),
  ).toBeVisible()

  // Ten per page unless chosen otherwise.
  await expect(page.getByText(/^1–10 de \d+$/)).toBeVisible()
  await page.getByRole('combobox', { name: 'Cantidad por página' }).selectOption('50 por página')
  await expect(page.getByRole('row', { name: new RegExp(`Importada ${run} 12`) })).toBeVisible()
  await expect(
    page.getByRole('combobox', { name: `Proyectos: Importada ${run} 1`, exact: true }),
  ).toHaveValue('editor')

  // A later file updates those already in the municipality.
  await page.getByRole('button', { name: 'Importar CSV' }).click()
  await dialog
    .locator('input[type="file"]')
    .setInputFiles(
      csvFile('cambios.csv', [
        'email,nombre,Proyectos',
        `${email(2)},Importada ${run} 2,Administración`,
      ]),
    )
  await dialog.getByRole('button', { name: 'Importar' }).click()
  await expect(page.getByText(/0 usuarios agregados, 1 actualizados/)).toBeVisible()
  await expect(
    page.getByRole('combobox', { name: `Proyectos: Importada ${run} 2`, exact: true }),
  ).toHaveValue('admin')
})

test('a file with mistakes changes nothing and says where they are', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()
  await page.getByRole('button', { name: 'Importar CSV' }).click()
  const dialog = page.getByRole('dialog')

  await dialog
    .locator('input[type="file"]')
    .setInputFiles(
      csvFile('mal.csv', [
        'email,nombre,Proyectos',
        'bien@noetinger.test,Bien,Lectura',
        'mal,Mal,Jefa',
      ]),
    )
  await dialog.getByRole('button', { name: 'Importar' }).click()

  await expect(dialog.getByText('El archivo tiene 2 problemas')).toBeVisible()
  await expect(dialog.getByRole('row', { name: /3 «mal» no es un email válido/ })).toBeVisible()
  await expect(dialog.getByText('No se cambió nada.', { exact: false })).toBeVisible()
  const users = await (await page.request.get('/api/admin/users?limit=200')).json()
  expect(users.items.map((m: { user: { email: string } }) => m.user.email)).not.toContain(
    'bien@noetinger.test',
  )
})

test('an administrator searches users and removes one after confirming in a modal', async ({
  page,
}) => {
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()
  // A browser popup would fail the test: removing asks in a modal window.
  page.on('dialog', (dialog) => {
    throw new Error(`Unexpected browser dialog: ${dialog.message()}`)
  })

  await page.getByRole('searchbox', { name: 'Buscar' }).fill('sofia')
  await expect(page.getByRole('row', { name: /Sofía Sin Acceso/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Leo Lectura/ })).toHaveCount(0)

  await page.getByRole('button', { name: 'Quitar a Sofía Sin Acceso' }).click()
  const question = page.getByRole('dialog', { name: 'Quitar usuario' })
  await expect(question).toContainText('¿Quitar a Sofía Sin Acceso de este municipio?')
  await question.getByRole('button', { name: 'Cancelar' }).click()
  await expect(page.getByRole('row', { name: /Sofía Sin Acceso/ })).toBeVisible()

  await page.getByRole('button', { name: 'Quitar a Sofía Sin Acceso' }).click()
  await question.getByRole('button', { name: 'Quitar' }).click()
  await expect(page.getByText('Nada coincide con la búsqueda.')).toBeVisible()
})

test('dashboard tables are searched and paged', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await page.goto('/d/projects/projects')
  const search = page.getByRole('searchbox', { name: 'Buscar' })

  await search.fill('plaza')
  await expect(page.getByRole('link', { name: 'Renovación de la plaza central' })).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Pavimentación de la calle San Martín' }),
  ).toHaveCount(0)

  await page.goto('/d/social/people')
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('zzz-nadie')
  await expect(page.getByText('No hay personas que coincidan.')).toBeVisible()
})
