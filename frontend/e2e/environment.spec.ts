import { expect, type Page, test } from '@playwright/test'

import { login, sidebar, statValue } from './helpers.ts'

const API = '/api/dashboards/environment'
const SOLAR = 'Energía solar generada'
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

async function openDashboard(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Ambiental' }).click()
  await expect(page.getByRole('heading', { name: 'Ambiental', level: 2 })).toBeVisible()
}

/** Values loaded so far this year, from the "3 / 13" headline card. */
async function loadedCount(page: Page): Promise<number> {
  const card = page.locator('[data-indicator]').filter({ hasText: 'Cargas del año' }).first()
  await expect(card).toContainText('/')
  return Number((await card.locator('p').nth(1).innerText()).split('/')[0].trim())
}

test('editor loads a value in the grid and the summary counts it', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  const loadedBefore = await loadedCount(page)

  // The demo leaves the current month empty.
  const month = MONTHS[new Date().getMonth()]
  await page.getByRole('tab', { name: 'Carga' }).click()
  const cell = page.getByRole('textbox', { name: `${SOLAR} — ${month}` })
  await expect(cell).toHaveValue('')
  await cell.fill('4321,5')
  await cell.blur()
  await page.reload()
  await expect(page.getByRole('textbox', { name: `${SOLAR} — ${month}` })).toHaveValue('4321,5')

  await page.getByRole('tab', { name: 'Resumen' }).click()
  await expect.poll(() => loadedCount(page)).toBe(loadedBefore + 1)

  await page.getByRole('tab', { name: 'Seguimiento' }).click()
  await page.getByRole('combobox', { name: 'Variable' }).selectOption({ label: SOLAR })
  await page.getByRole('button', { name: 'Ver como tabla' }).click()
  await expect(page.getByRole('row', { name: new RegExp(month) })).toContainText('4.321,5 kWh')
})

test('viewer reads the dashboard but cannot load values or change parameters', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  await expect(page.getByRole('row', { name: new RegExp(SOLAR) })).toBeVisible()
  await expect(page.getByText('Categorías sin variables: Aire.')).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Carga' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'Parámetros' })).toHaveCount(0)

  const variables = await (await page.request.get(`${API}/variables`)).json()
  const response = await page.request.put(`${API}/values`, {
    headers: { 'X-Requested-With': 'gobernar360' },
    data: { variable_id: variables[0].id, year: 2026, period: 1, value: '1' },
  })
  expect(response.status()).toBe(403)
})

test('dashboard admin defines a new variable and it appears in the entry grid', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)
  await page.getByRole('tab', { name: 'Parámetros' }).click()

  await page.getByRole('combobox', { name: 'Categoría' }).selectOption({ label: 'Aire' })
  await page.getByLabel('Nueva subcategoría').fill('Calidad del aire')
  await page.getByRole('button', { name: 'Agregar', exact: true }).click()
  await page.getByRole('button', { name: 'Agregar variable' }).click()
  const form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Nombre' }).fill('Material particulado E2E')
  await form.getByRole('textbox', { name: 'Unidad' }).fill('µg/m³')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Material particulado E2E/ })).toBeVisible()

  await page.getByRole('tab', { name: 'Carga' }).click()
  await expect(
    page.getByRole('textbox', { name: 'Material particulado E2E — Enero' }),
  ).toBeVisible()
})

test('overview shows the environment indicators', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')

  await expect(page.getByRole('heading', { name: 'Resumen general' })).toBeVisible()
  expect(await statValue(page, 'Variables ambientales')).toBeGreaterThan(0)
  expect(await statValue(page, 'Metas ambientales cumplidas')).toBeGreaterThan(0)
  await expect(page.getByText('Cargas del año realizadas')).toBeVisible()
})

test("the second municipality sees none of the first municipality's variables", async ({
  page,
}) => {
  await login(page, 'admin@comuna-demo.test')
  await openDashboard(page)

  await expect(page.getByText('Todavía no hay variables definidas')).toBeVisible()
  expect(await (await page.request.get(`${API}/variables`)).json()).toEqual([])
  const csv = await (await page.request.get(`${API}/export/values.csv`)).text()
  expect(csv).not.toContain(SOLAR)
})

test('values csv download contains the seeded values', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Descargar valores' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(`environment-values-${new Date().getFullYear()}.csv`)
})
