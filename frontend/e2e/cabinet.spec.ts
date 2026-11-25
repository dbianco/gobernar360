import { readFile } from 'node:fs/promises'

import { expect, type Page, test } from '@playwright/test'

import { choosePerson, login, logout, sidebar, statValue } from './helpers.ts'

const MONTHS = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
]
const now = new Date()
const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
const MONTH = MONTHS[lastMonth.getMonth()]
const LIGHT_ITEM = `Ambiental, ${MONTH.toLowerCase()} de ${lastMonth.getFullYear()}`
const STATUS_URL = `/api/dashboards/environment/status/${lastMonth.getFullYear()}/${lastMonth.getMonth() + 1}`
const HEADERS = { 'X-Requested-With': 'gobernar360' }

const PROJECT = 'Renovación de la plaza central'
const ABOUT_PROJECT = 'Renovar los bancos de la plaza'
const ABOUT_LIGHT = 'Reparar la balanza del predio'
const OVERDUE = [
  'Certificar la segunda etapa de la pavimentación',
  'Habilitar en línea la renovación de licencias de conducir',
]

const pad = (value: number) => String(value).padStart(2, '0')

/** Today as an ISO date. */
const TODAY = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`

/** A date some days from today, as a person writes it. */
function inDays(days: number): string {
  const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + days)
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`
}

const openCommitments = (page: Page) => page.getByRole('region', { name: 'Compromisos pendientes' })

async function openCabinet(page: Page, tab?: string) {
  await sidebar(page).getByRole('link', { name: 'Gabinete' }).click()
  await expect(page.getByRole('heading', { name: 'Gabinete', level: 2 })).toBeVisible()
  if (tab) await page.getByRole('tab', { name: tab, exact: true }).click()
}

async function setGrants(page: Page, grants: Record<string, string>) {
  const found = await (await page.request.get('/api/admin/users?q=sinacceso')).json()
  const response = await page.request.patch(`/api/admin/users/${found.items[0].membership_id}`, {
    headers: HEADERS,
    data: { grants },
  })
  expect(response.status()).toBe(200)
}

// One story, from preparing a meeting to the next one: each step needs the one before.
test.describe.configure({ mode: 'serial' })

// Other specs count on this member having no access and on last month as it was seeded,
// also when one of these fails.
test.afterAll(async ({ browser }) => {
  const page = await browser.newPage()
  await login(page, 'admin@noetinger.test')
  await setGrants(page, {})
  await page.request.put(STATUS_URL, { headers: HEADERS, data: { color: 'green' } })
  await page.close()
})

test('the proposed agenda has the red dashboard and every overdue commitment', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  // Setting lights in their strip is status.spec.ts; this month's stays in order.
  const set = await page.request.put(STATUS_URL, { headers: HEADERS, data: { color: 'red' } })
  expect(set.status()).toBe(204)
  await openCabinet(page, 'Reuniones')

  await page.getByRole('link', { name: 'Preparar reunión' }).click()

  await expect(page.getByRole('checkbox', { name: LIGHT_ITEM })).toBeChecked()
  for (const name of OVERDUE) await expect(page.getByRole('checkbox', { name })).toBeChecked()
  await expect(page.getByRole('checkbox', { name: 'Cronograma de fin de año' })).toBeChecked()
  // Still in time, so not proposed.
  await expect(
    page.getByRole('checkbox', { name: 'Convocar a la mesa de emprendedores' }),
  ).toHaveCount(0)

  // Accept, drop, add and reorder.
  await page.getByRole('checkbox', { name: 'Cronograma de fin de año' }).uncheck()
  await page.getByLabel('Tema propio', { exact: true }).fill('Plaza central')
  await page.getByRole('button', { name: 'Agregar', exact: true }).click()
  const item = (name: string) =>
    page.getByRole('listitem').filter({ has: page.getByRole('checkbox', { name }) })
  await item('Plaza central').getByRole('button', { name: 'Subir' }).click()
  await page.getByRole('combobox', { name: 'Participantes' }).click()
  await page.getByRole('option', { name: 'Ana Administradora' }).click()
  await page.getByRole('button', { name: 'Crear reunión' }).click()

  await expect(page.getByRole('heading', { name: /^Reunión del/ })).toBeVisible()
  await expect(page.getByText('Ana Administradora', { exact: true }).first()).toBeVisible()
  const agenda = page.getByRole('region', { name: 'Temario' })
  await expect(agenda.getByRole('heading', { level: 5 }).first()).toContainText(LIGHT_ITEM)
  await expect(agenda.getByRole('heading', { name: 'Cronograma de fin de año' })).toHaveCount(0)
  await expect(agenda.getByRole('heading', { level: 5 }).last()).toContainText('Plaza central')
})

test('commitments appear on the project and beside the red month they are about', async ({
  page,
}) => {
  await login(page, 'carga@noetinger.test')
  await openCabinet(page, 'Reuniones')
  await page.getByRole('link', { name: /^Continuar la reunión/ }).click()
  const form = page.getByRole('dialog')
  const owner = form.getByRole('combobox', { name: 'Responsable' })

  await page.getByRole('button', { name: 'Agregar compromiso en Plaza central' }).click()
  await form.getByLabel('Qué hay que hacer').fill(ABOUT_PROJECT)
  await choosePerson(page, owner, 'leo', 'Leo Lectura')
  await form.getByLabel('Fecha comprometida').fill(inDays(20))
  await form.getByLabel('Vinculado a').selectOption({ label: 'Proyectos: proyecto' })
  await form.getByRole('combobox', { name: 'Cuál' }).fill('plaza')
  await page.getByRole('option', { name: PROJECT }).click()
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()

  // The item about the light already knows what its commitments are about.
  await page.getByRole('button', { name: `Agregar compromiso en ${LIGHT_ITEM}` }).click()
  await form.getByLabel('Qué hay que hacer').fill(ABOUT_LIGHT)
  await choosePerson(page, owner, 'carga', 'Carla Carga')
  await form.getByLabel('Fecha comprometida').fill(inDays(10))
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await page.getByRole('textbox', { name: `Notas de ${LIGHT_ITEM}` }).fill('Se rompió la balanza.')

  const plaza = page.getByRole('region', { name: 'Plaza central' })
  await plaza.getByRole('link', { name: PROJECT }).click()
  await expect(page.getByRole('heading', { name: PROJECT })).toBeVisible()
  await expect(openCommitments(page)).toContainText(ABOUT_PROJECT)
  await expect(openCommitments(page)).toContainText('Leo Lectura')

  await sidebar(page).getByRole('link', { name: 'Ambiental' }).click()
  await page.getByRole('combobox', { name: 'Año' }).selectOption(String(lastMonth.getFullYear()))
  const month = openCommitments(page).getByRole('group', { name: `${MONTH}: Crítico` })
  await expect(month).toContainText(ABOUT_LIGHT)
  await month.getByRole('link', { name: ABOUT_LIGHT }).click()
  await expect(page.getByRole('heading', { name: ABOUT_LIGHT })).toBeVisible()
})

test('a closed meeting has minutes and can no longer be edited', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openCabinet(page, 'Reuniones')
  await page.getByRole('link', { name: /^Continuar la reunión/ }).click()
  // What was written in the previous step was saved by leaving it.
  await expect(page.getByRole('textbox', { name: `Notas de ${LIGHT_ITEM}` })).toHaveValue(
    'Se rompió la balanza.',
  )
  const id = page.url().split('/').pop()

  await page.getByRole('button', { name: 'Cerrar reunión' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Cerrar reunión' }).click()

  const minutes = page.getByRole('link', { name: 'Descargar acta' })
  const [download] = await Promise.all([page.waitForEvent('download'), minutes.click()])
  expect(download.suggestedFilename()).toBe(`acta-gabinete-${TODAY}.html`)
  const text = await readFile(await download.path(), 'utf8')
  for (const piece of [
    `${LIGHT_ITEM} (crítico)`,
    'Se rompió la balanza.',
    ABOUT_LIGHT,
    ABOUT_PROJECT,
    `Sobre: ${PROJECT}`,
    'Reunión cerrada por Ana Administradora',
  ]) {
    expect(text).toContain(piece)
  }

  await expect(page.getByRole('textbox')).toHaveCount(0)
  await expect(page.getByRole('checkbox')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Agregar tema' })).toHaveCount(0)
  const refused = await page.request.patch(`/api/dashboards/cabinet/meetings/${id}`, {
    headers: HEADERS,
    data: { notes: 'Otra cosa' },
  })
  expect(refused.status()).toBe(409)
  expect((await refused.json()).error.code).toBe('meeting_closed')
})

test('what was not done is carried over to the next meeting, postponed once', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openCabinet(page, 'Reuniones')
  await page.getByRole('link', { name: 'Preparar reunión' }).click()
  // Nobody discussed it in the meeting that just closed.
  await expect(page.getByRole('checkbox', { name: OVERDUE[0] })).toBeChecked()
  await page.getByRole('button', { name: 'Crear reunión' }).click()

  const carried = page.getByRole('region', { name: 'Compromisos arrastrados' })
  await expect(carried.getByRole('link', { name: ABOUT_PROJECT })).toBeVisible()
  await carried.getByRole('link', { name: ABOUT_LIGHT }).click()

  await expect(page.getByRole('heading', { name: ABOUT_LIGHT })).toBeVisible()
  await expect(page.getByText('Postergado 1 vez')).toBeVisible()
})

test('an editor marks it done and it leaves the month and the pending ones', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openCabinet(page)
  const doneBefore = await statValue(page, 'Cumplidos')
  await page.getByRole('tab', { name: 'Compromisos', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('balanza')
  await page.getByRole('link', { name: ABOUT_LIGHT }).click()

  await page.getByRole('button', { name: 'Marcar cumplido' }).click()
  await page.getByRole('dialog').getByLabel('Nota').fill('Balanza nueva instalada.')
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click()

  const history = page.getByRole('region', { name: 'Avance e historial' })
  await expect(history).toContainText('Balanza nueva instalada.')
  await expect(history).toContainText('Estado: Pendiente → Cumplido')
  await sidebar(page).getByRole('link', { name: 'Ambiental' }).click()
  await page.getByRole('combobox', { name: 'Año' }).selectOption(String(lastMonth.getFullYear()))
  await expect(page.getByRole('region', { name: 'Estado mensual' })).toBeVisible()
  await expect(page.getByText(ABOUT_LIGHT)).toHaveCount(0)
  await openCabinet(page)
  await expect.poll(() => statValue(page, 'Cumplidos')).toBe(doneBefore + 1)
})

test('a viewer follows their own commitments and adds notes to them', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openCabinet(page, 'Reuniones')
  await expect(page.getByRole('link', { name: /Preparar|Continuar/ })).toHaveCount(0)
  await sidebar(page).getByRole('link', { name: 'Compromisos' }).click()
  await page.getByRole('link', { name: ABOUT_PROJECT }).click()

  await page.getByLabel('Nota de avance').fill('Pedí los presupuestos.')
  await page.getByRole('button', { name: 'Agregar nota' }).click()

  await expect(page.getByRole('region', { name: 'Avance e historial' })).toContainText(
    'Leo Lectura',
  )
  // Whoever owes it says it is done; dropping it is for those who record the meetings.
  await expect(page.getByRole('button', { name: 'Marcar cumplido' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Descartar' })).toHaveCount(0)
})

test('a member without Projects sees the commitment but not which project', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await setGrants(page, { cabinet: 'viewer' })
  await logout(page)
  await login(page, 'sinacceso@noetinger.test')
  await openCabinet(page, 'Compromisos')

  const row = page.getByRole('row', { name: new RegExp(ABOUT_PROJECT) })
  await expect(row).toContainText('Un proyecto al que no tenés acceso')
  await expect(page.getByText(PROJECT)).toHaveCount(0)
  await row.getByRole('link', { name: ABOUT_PROJECT }).click()
  await expect(page.getByRole('heading', { name: ABOUT_PROJECT })).toBeVisible()
  await expect(page.getByText('Un proyecto al que no tenés acceso')).toBeVisible()
  const csv = await (
    await page.request.get('/api/dashboards/cabinet/export/commitments.csv')
  ).text()
  expect(csv).toContain(ABOUT_PROJECT)
  expect(csv).not.toContain(PROJECT)
})

test('the second municipality has the dashboard and none of this data', async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')
  await openCabinet(page)

  await expect(page.getByText('Todavía no hay compromisos')).toBeVisible()
  await page.getByRole('tab', { name: 'Reuniones' }).click()
  await expect(page.getByText('Todavía no hay reuniones.')).toBeVisible()
})
