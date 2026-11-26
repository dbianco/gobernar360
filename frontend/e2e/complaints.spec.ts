import { expect, type Page, test } from '@playwright/test'

import { login, logout, openUsers, sidebar } from './helpers.ts'

const API = '/api/dashboards/complaints'
const ADDRESS = 'Belgrano 999'
const CSRF = { 'X-Requested-With': 'gobernar360' }

async function openDashboard(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Reclamos' }).click()
  await expect(page.getByRole('heading', { name: 'Reclamos', level: 2 })).toBeVisible()
}

const tab = (page: Page, name: string) => page.getByRole('tab', { name, exact: true })
const actions = (page: Page) => page.getByRole('region', { name: 'Acciones' })
const history = (page: Page) => page.getByRole('region', { name: 'Historial' })

/** The value shown under a label of the service clock panel. */
async function clockValue(page: Page, name: string): Promise<string> {
  const value = page
    .getByRole('region', { name: 'Reloj de servicio' })
    .getByText(name, { exact: true })
    .locator('xpath=following-sibling::*[1]')
  return value.innerText()
}

async function move(page: Page, action: string, note = '') {
  await actions(page).getByRole('button', { name: action }).click()
  const dialog = page.getByRole('dialog')
  if (note) await dialog.getByRole('textbox', { name: 'Nota' }).fill(note)
  await dialog.getByRole('button', { name: action }).click()
  await expect(dialog).toBeHidden()
}

/** Open the complaint filed at ADDRESS from the list. */
async function openFiledComplaint(page: Page) {
  await tab(page, 'Reclamos').click()
  await page.getByRole('textbox', { name: 'Buscar' }).fill(ADDRESS)
  const row = page.getByRole('row', { name: new RegExp(ADDRESS) })
  await row.getByRole('link', { name: /Abrir reclamo/ }).click()
  await expect(page.getByRole('heading', { name: /Reclamo N\.º \d+/ })).toBeVisible()
  return page.url().split('/').pop() as string
}

/** Rows of a CSV file, honouring quoted fields (names are written "Apellido, Nombre"). */
function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  const input = text.replace(/^\uFEFF/, '')
  for (let index = 0; index < input.length; index++) {
    const char = input[index]
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') {
        field += '"'
        index++
      } else if (char === '"') quoted = false
      else field += char
    } else if (char === '"') quoted = true
    else if (char === ',') {
      row.push(field)
      field = ''
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && input[index + 1] === '\n') index++
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else field += char
  }
  if (field || row.length) rows.push([...row, field])
  return rows
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = (sorted.length - 1) / 2
  return (sorted[Math.floor(middle)] + sorted[Math.ceil(middle)]) / 2
}

test('the operator enables Reclamos for Noetinger', async ({ page }) => {
  await login(page, 'operador@gobernar360.test')
  await page.getByRole('link', { name: 'Configurar Noetinger' }).click()

  const dashboard = page.getByRole('checkbox', { name: 'Reclamos' })
  await expect(dashboard).not.toBeChecked()
  await dashboard.click()
  await expect(dashboard).toBeChecked()
})

test('a complaint for a resident found by document lands in its area queue', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)

  await tab(page, 'Reclamos').click()
  await page.getByRole('button', { name: 'Nuevo reclamo' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Tipo de reclamo').selectOption({ label: 'Luminaria apagada' })
  await expect(
    form.getByText('Se deriva a Alumbrado Público, con un plazo de 3 días hábiles.'),
  ).toBeVisible()
  await form.getByLabel('Zona').selectOption({ label: 'Centro' })
  await form.getByRole('textbox', { name: 'Dirección' }).fill(ADDRESS)
  await form.getByText('Vecino con DNI').click()
  await form.getByRole('textbox', { name: 'DNI o CUIL del vecino' }).fill('33.123.456')
  await form.getByRole('button', { name: 'Buscar en el padrón' }).click()
  await expect(
    form.getByText('Se registra a nombre de Fernández, Lucía (DNI 33.123.456).'),
  ).toBeVisible()
  await form.getByRole('button', { name: 'Guardar' }).click()

  const heading = page.getByRole('heading', { name: /Reclamo N\.º \d+/ })
  await expect(heading).toBeVisible()
  const number = (await heading.innerText()).replace(/\D/g, '')
  await expect(page.getByText('Fernández, Lucía · DNI 33.123.456')).toBeVisible()
  await expect(page.getByText('Alumbrado Público', { exact: true })).toBeVisible()
  const deadline = await clockValue(page, 'Vence')
  expect(deadline).toMatch(/^\d{2}\/\d{2}\/\d{4}$/)

  await tab(page, 'Bandejas').click()
  await page.getByRole('button', { name: 'Ver bandeja de Alumbrado Público' }).click()
  const queue = page.getByRole('table', { name: 'Bandeja de Alumbrado Público' })
  const row = queue.getByRole('row', { name: new RegExp(ADDRESS) })
  await expect(row.getByRole('link', { name: `Abrir reclamo ${number}` })).toBeVisible()
  await expect(row).toContainText(deadline)
  await expect(row).toContainText('Recibido')
})

test('the complaint goes from received to closed, and waiting costs no time', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)
  const id = await openFiledComplaint(page)

  // Never resolved: closing is neither offered nor accepted.
  await expect(actions(page).getByRole('button', { name: 'Cerrar' })).toHaveCount(0)
  const refused = await page.request.post(`${API}/complaints/${id}/transitions`, {
    data: { to_state: 'closed' },
    headers: CSRF,
  })
  expect(refused.status()).toBe(409)
  expect((await refused.json()).error.code).toBe('invalid_transition')

  await move(page, 'Asignar al área')
  await move(page, 'Empezar a trabajar', 'Cuadrilla en camino')
  const leftBefore = await clockValue(page, 'Restan')
  await move(page, 'Esperar al vecino', 'Pedimos la altura exacta')
  await expect(
    page.getByText('El reloj está detenido mientras se espera al vecino', { exact: false }),
  ).toBeVisible()
  expect(await clockValue(page, 'Restan')).toBe(leftBefore)
  await move(page, 'Retomar: el vecino respondió', 'El vecino respondió')
  expect(await clockValue(page, 'Restan')).toBe(leftBefore)
  await expect(actions(page).getByRole('button', { name: 'Cerrar' })).toHaveCount(0)
  await move(page, 'Marcar como resuelto', 'Se cambió la lámpara')
  await move(page, 'Cerrar', 'El vecino confirmó')

  await expect(page.getByText('Cerrado', { exact: true })).toBeVisible()
  await expect(actions(page).getByRole('button')).toHaveText(['Agregar nota'])
  for (const step of [
    'Recibido y derivado a Alumbrado Público',
    'Recibido → Asignado',
    'Asignado → En curso',
    'En curso → Esperando al vecino',
    'Pedimos la altura exacta',
    'Esperando al vecino → En curso',
    'El vecino respondió',
    'En curso → Resuelto',
    'Resuelto → Cerrado',
  ]) {
    await expect(history(page).getByText(step, { exact: true })).toBeVisible()
  }
  await expect(history(page)).toContainText('Ana Administradora')
})

test('the summary median by type matches the cases download', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)

  const byType = page.getByRole('table', { name: 'Tiempo de resolución por tipo' })
  const row = byType.getByRole('row', { name: /^Bache/ })
  const shown = Number((await row.getByRole('cell').nth(4).innerText()).replace(',', '.'))
  const href = await page
    .getByRole('link', { name: 'Descargar reclamos del período' })
    .getAttribute('href')
  const csv = await (await page.request.get(href as string)).text()

  const [columns, ...rows] = parseCsv(csv)
  const type = columns.indexOf('type')
  const days = columns.indexOf('resolution_business_days')
  const values = rows
    .filter((cells) => cells[type] === 'Bache' && cells[days] !== '')
    .map((cells) => Number(cells[days]))
  expect(values.length).toBeGreaterThan(10)
  expect(median(values)).toBe(shown)
})

test('once granted, the viewer reads complaints but cannot change them', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openUsers(page)
  const access = page.getByRole('combobox', { name: 'Reclamos: Leo Lectura' })
  await access.selectOption({ label: 'Lectura' })
  await expect(access).toHaveValue('viewer')
  await logout(page)

  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)
  await expect(tab(page, 'Parámetros')).toHaveCount(0)
  const id = await openFiledComplaint(page)

  await expect(history(page).getByText('Resuelto → Cerrado')).toBeVisible()
  await expect(actions(page)).toHaveCount(0)
  await tab(page, 'Reclamos').click()
  await expect(page.getByRole('button', { name: 'Nuevo reclamo' })).toHaveCount(0)
  const refused = await page.request.post(`${API}/complaints/${id}/comments`, {
    data: { note: 'intento' },
    headers: CSRF,
  })
  expect(refused.status()).toBe(403)
})

test("the other municipality sees none of Noetinger's complaints", async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  const found = await (
    await page.request.get(`${API}/complaints`, { params: { q: ADDRESS } })
  ).json()
  const id = found.items[0].id
  await logout(page)

  await login(page, 'admin@comuna-demo.test')
  await openDashboard(page)
  await tab(page, 'Reclamos').click()

  const rows = page.getByRole('table', { name: 'Reclamos' }).getByRole('row')
  // A header and the commune's own four complaints.
  await expect(rows).toHaveCount(5)
  await expect(page.getByText(ADDRESS)).toHaveCount(0)
  expect((await page.request.get(`${API}/complaints/${id}`)).status()).toBe(404)
  const search = await (
    await page.request.get(`${API}/complaints`, { params: { q: ADDRESS } })
  ).json()
  expect(search.total).toBe(0)
})
