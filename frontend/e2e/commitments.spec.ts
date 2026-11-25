import { expect, type Page, test } from '@playwright/test'

import { choosePerson, login, logout, sidebar } from './helpers.ts'

const TASK = 'Llamar al contratista de la plaza'
const OWN = 'Ordenar el archivo'
const PASSED_ON = 'Revisar el presupuesto de la feria'
const now = new Date()
const pad = (value: number) => String(value).padStart(2, '0')

/** A date some days from today, as a person writes it. */
function inDays(days: number): string {
  const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + days)
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`
}

const mineIcon = (page: Page) => page.getByRole('link', { name: /^Compromisos a mi cargo:/ })
const newsIcon = (page: Page) => page.getByRole('link', { name: /^Notificaciones:/ })
const section = (page: Page, name: string) => page.getByRole('region', { name })
const people = (page: Page) =>
  page.getByRole('listbox', { name: 'Responsable' }).getByRole('option')
const MINE = 'Compromisos a mi cargo'
const OTHERS = 'Compromisos de otros que sigo'

async function openNotifications(page: Page) {
  await newsIcon(page).click()
  await expect(page.getByRole('heading', { name: 'Notificaciones' })).toBeVisible()
}

async function signInAs(page: Page, name: string) {
  if (await page.getByRole('button', { name: 'Cerrar sesión' }).isVisible()) await logout(page)
  await login(page, `${name}@noetinger.test`)
}

interface Task {
  what: string
  owner: [typed: string, name: string]
  attached?: [typed: string, name: string][]
}

async function give(page: Page, { what, owner, attached = [] }: Task) {
  await sidebar(page).getByRole('link', { name: 'Compromisos' }).click()
  await page.getByRole('button', { name: 'Nuevo compromiso' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Qué hay que hacer').fill(what)
  await choosePerson(page, form.getByRole('combobox', { name: 'Responsable' }), ...owner)
  await form.getByLabel('Fecha comprometida').fill(inDays(5))
  for (const person of attached) {
    await choosePerson(page, form.getByRole('combobox', { name: /^Avisar/ }), ...person)
  }
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
}

// One story: each step needs the one before.
test.describe.configure({ mode: 'serial' })

test('anyone gives anyone a commitment, finding the names by typing', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Compromisos' }).click()
  await page.getByRole('button', { name: 'Nuevo compromiso' }).click()
  const form = page.getByRole('dialog')
  const owner = form.getByRole('combobox', { name: 'Responsable' })
  await owner.fill('sofia')
  // Without the accent, and nobody else.
  await expect(people(page)).toHaveText(['Sofía Sin Acceso'])
  await form.getByRole('button', { name: 'Cancelar' }).click()

  await give(page, {
    what: TASK,
    owner: ['sofia', 'Sofía Sin Acceso'],
    attached: [['ana', 'Ana Administradora']],
  })

  await page.getByRole('tab', { name: 'Los que asigné' }).click()
  const row = page.getByRole('row', { name: new RegExp(TASK) })
  await expect(row).toContainText('Sofía Sin Acceso')
  await expect(row).toContainText(inDays(5))
  await expect(row).toContainText('Informal')
})

test('whoever is given one sees it beside their name, without any dashboard', async ({ page }) => {
  await login(page, 'sinacceso@noetinger.test')

  await expect(newsIcon(page)).toHaveAccessibleName('Notificaciones: 1 novedad')
  await newsIcon(page).hover()
  await expect(page.getByText('Carla Carga te lo asignó')).toBeVisible()
  await openNotifications(page)
  const row = section(page, MINE).getByRole('row', { name: new RegExp(TASK) })
  await expect(row).toContainText('Pendiente')
  await expect(row).toContainText(inDays(5))
  await row.getByRole('link', { name: TASK }).click()

  await expect(page.getByRole('heading', { name: TASK })).toBeVisible()
  // Opening it is reading about it.
  await expect(newsIcon(page)).toHaveAccessibleName('Notificaciones: 0 novedades')
  await expect(mineIcon(page)).toHaveAccessibleName(/1 pendiente$/)
})

test('those attached follow it and are told when it is done', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openNotifications(page)
  const row = section(page, OTHERS).getByRole('row', { name: new RegExp(TASK) })
  await expect(row).toContainText('Pendiente')
  await row.getByRole('link', { name: TASK }).click()
  // They read it; it is not theirs to change.
  await expect(page.getByRole('heading', { name: TASK })).toBeVisible()
  for (const name of ['Marcar cumplido', 'Editar', 'Descartar']) {
    await expect(page.getByRole('button', { name })).toHaveCount(0)
  }

  await signInAs(page, 'sinacceso')
  await sidebar(page).getByRole('link', { name: 'Compromisos' }).click()
  await page.getByRole('link', { name: TASK }).click()
  await page.getByRole('button', { name: 'Marcar cumplido' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Cumplido', { exact: true })).toBeVisible()

  // Whoever gave it is told too.
  for (const name of ['admin', 'carga']) {
    await signInAs(page, name)
    await openNotifications(page)
    const done = section(page, OTHERS).getByRole('row', { name: new RegExp(TASK) })
    await expect(done).toContainText('Sofía Sin Acceso lo cumplió')
    await page.getByRole('button', { name: `Marcar como leída: ${TASK}` }).click()
    await expect(done).toHaveCount(0)
  }
})

test('nobody else sees it, not even the administrator or the cabinet', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await give(page, { what: PASSED_ON, owner: ['leo', 'Leo Lectura'] })
  await page.getByRole('tab', { name: 'Los que asigné' }).click()
  await page.getByRole('link', { name: PASSED_ON }).click()
  await expect(page.getByRole('heading', { name: PASSED_ON })).toBeVisible()
  const url = page.url()

  await signInAs(page, 'admin')
  await page.goto(url)
  await expect(page.getByText('No se encontró el registro.')).toBeVisible()
  await sidebar(page).getByRole('link', { name: 'Gabinete' }).click()
  await page.getByRole('tab', { name: 'Compromisos' }).click()
  await expect(page.getByRole('table', { name: 'Compromisos' })).toBeVisible()
  await page.getByRole('searchbox').fill('feria')
  await expect(page.getByText('Ningún compromiso coincide.')).toBeVisible()
})

test('whoever owes one changes its date and passes it on', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Compromisos' }).click()
  await page.getByRole('link', { name: PASSED_ON }).click()
  await page.getByRole('button', { name: 'Editar' }).click()
  const form = page.getByRole('dialog')
  await expect(form.getByLabel('Qué hay que hacer')).toBeDisabled()
  await form.getByLabel('Fecha comprometida').fill(inDays(9))
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('region', { name: 'Avance e historial' })).toContainText(
    `Fecha comprometida: ${inDays(5)} → ${inDays(9)}`,
  )

  await page.getByRole('button', { name: 'Editar' }).click()
  await choosePerson(
    page,
    form.getByRole('combobox', { name: 'Responsable' }),
    'sin acceso',
    'Sofía Sin Acceso',
  )
  await form.getByRole('button', { name: 'Guardar' }).click()
  // No longer theirs to look at.
  await expect(page.getByRole('heading', { name: 'Compromisos', level: 2 })).toBeVisible()
  await expect(page.getByRole('link', { name: PASSED_ON })).toHaveCount(0)

  await signInAs(page, 'sinacceso')
  await openNotifications(page)
  await expect(section(page, MINE).getByRole('row', { name: new RegExp(PASSED_ON) })).toContainText(
    'Leo Lectura te lo asignó',
  )
})

test('anyone gives themselves one and closes it', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await give(page, { what: OWN, owner: ['lectura', 'Leo Lectura'] })

  await mineIcon(page).hover()
  await expect(page.getByText('Ver la lista completa')).toBeVisible()
  await page.getByRole('heading', { name: 'Compromisos', level: 2 }).hover()
  await page.getByRole('row', { name: new RegExp(OWN) }).getByRole('link', { name: OWN }).click()
  await page.getByRole('button', { name: 'Marcar cumplido' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Cumplido', { exact: true })).toBeVisible()
  await openNotifications(page)
  await expect(page.getByText(OWN)).toHaveCount(0)
})

test('the other municipality sees none of it', async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')

  await openNotifications(page)

  await expect(page.getByText('No tenés compromisos pendientes.')).toBeVisible()
  await expect(
    page.getByText('No seguís compromisos pendientes de otras personas.'),
  ).toBeVisible()
  await sidebar(page).getByRole('link', { name: 'Compromisos' }).click()
  await page.getByRole('button', { name: 'Nuevo compromiso' }).click()
  await page.getByRole('dialog').getByRole('combobox', { name: 'Responsable' }).click()
  await expect(people(page)).toHaveText(['Andrés Administrador'])
})
