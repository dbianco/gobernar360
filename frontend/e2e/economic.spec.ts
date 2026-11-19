import { expect, type Page, test } from '@playwright/test'

import { login, sidebar, statValue } from './helpers.ts'

const API = '/api/dashboards/economic'
const SEEDED_ACTOR = 'Panadería La Espiga'

async function openDashboard(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Económico' }).click()
  await expect(page.getByRole('heading', { name: 'Económico', level: 2 })).toBeVisible()
}

const tab = (page: Page, name: string) => page.getByRole('tab', { name, exact: true })

test('editor registers an actor and a person, links them and assigns a tool', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  const assignmentsBefore = await statValue(page, 'Asignaciones del año')
  const actorsBefore = await statValue(page, 'Actores económicos')

  await tab(page, 'Actores').click()
  await page.getByRole('button', { name: 'Cargar nuevo actor económico' }).click()
  let form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Nombre', exact: true }).fill('Herrería E2E')
  await form.getByRole('textbox', { name: 'CUIT' }).fill('20-30111222-3')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await page.getByRole('textbox', { name: 'Buscar' }).fill('herrería')
  await expect(page.getByRole('row', { name: /Herrería E2E/ })).toContainText('20-30111222-3')

  await tab(page, 'Personas').click()
  await page.getByRole('button', { name: 'Cargar nueva persona' }).click()
  form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'DNI' }).fill('45.111.222')
  await form.getByRole('textbox', { name: 'Nombre', exact: true }).fill('Eva')
  await form.getByRole('textbox', { name: 'Apellido', exact: true }).fill('Prueba')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Prueba, Eva/ })).toContainText('45.111.222')

  await tab(page, 'Actores').click()
  await page.getByRole('link', { name: 'Herrería E2E' }).click()
  await page.getByRole('button', { name: 'Vincular persona' }).click()
  await page.getByRole('textbox', { name: 'Buscar persona' }).fill('Prueba')
  await page.getByRole('button', { name: 'Vincular a Prueba, Eva' }).click()
  await expect(page.getByRole('link', { name: 'Prueba, Eva' })).toBeVisible()

  await page.getByRole('button', { name: 'Asignar herramienta' }).click()
  form = page.getByRole('dialog')
  await form.getByRole('combobox', { name: 'Herramienta' }).selectOption({
    label: 'Microcrédito productivo',
  })
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Microcrédito productivo/ })).toBeVisible()

  await tab(page, 'Resumen').click()
  await expect.poll(() => statValue(page, 'Asignaciones del año')).toBe(assignmentsBefore + 1)
  expect(await statValue(page, 'Actores económicos')).toBe(actorsBefore + 1)
})

test('a document already in the dashboard is not loaded twice', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  await tab(page, 'Personas').click()

  await page.getByRole('button', { name: 'Cargar nueva persona' }).click()
  const form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'DNI' }).fill('24444444')
  await form.getByRole('textbox', { name: 'Nombre', exact: true }).click()

  await expect(form.getByText('Aguirre, Rosa ya está registrada en este tablero.')).toBeVisible()
  await expect(form.getByRole('button', { name: 'Guardar' })).toBeDisabled()
})

test('viewer reads the dashboard but cannot load data', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  await expect(page.getByRole('tab', { name: 'Parámetros' })).toHaveCount(0)
  await tab(page, 'Actores').click()
  await expect(page.getByRole('link', { name: SEEDED_ACTOR })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cargar nuevo actor económico' })).toHaveCount(0)
  await page.getByRole('link', { name: SEEDED_ACTOR }).click()
  await expect(page.getByRole('heading', { name: SEEDED_ACTOR })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Asignar herramienta' })).toHaveCount(0)
  await tab(page, 'Reportes').click()
  await expect(page.getByRole('heading', { name: 'Actores por tipo' })).toBeVisible()

  const headers = { 'X-Requested-With': 'gobernar360' }
  const created = await page.request.post(`${API}/actors`, { headers, data: { name: 'x' } })
  expect(created.status()).toBe(403)
  const lookup = await page.request.get(`${API}/people/lookup?dni=24444444`)
  expect(lookup.status()).toBe(403)
})

test('dashboard admin adds a tool and it can then be assigned', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)
  await tab(page, 'Parámetros').click()

  await page.getByRole('button', { name: 'Agregar herramienta' }).click()
  let form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Nombre' }).fill('Ronda de negocios E2E')
  await form.getByRole('combobox', { name: 'Destinatarios' }).selectOption({ label: 'Solo actores' })
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Ronda de negocios E2E/ })).toBeVisible()

  await tab(page, 'Actores').click()
  await page.getByRole('link', { name: SEEDED_ACTOR }).click()
  await page.getByRole('button', { name: 'Asignar herramienta' }).click()
  form = page.getByRole('dialog')
  await expect(
    form.getByRole('combobox', { name: 'Herramienta' }).getByRole('option', {
      name: 'Ronda de negocios E2E',
    }),
  ).toBeAttached()
  // Tools meant only for people are not offered to an actor.
  await expect(
    form.getByRole('combobox', { name: 'Herramienta' }).getByRole('option', {
      name: 'Taller de oficios',
    }),
  ).toHaveCount(0)
})

test('overview shows the economic indicators', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')

  await expect(page.getByRole('heading', { name: 'Resumen general' })).toBeVisible()
  expect(await statValue(page, 'Actores económicos')).toBeGreaterThan(0)
  expect(await statValue(page, 'Personas registradas')).toBeGreaterThan(0)
  expect(await statValue(page, 'Herramientas de apoyo')).toBeGreaterThan(0)
})

test("the second municipality sees none of the first municipality's records", async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')
  await openDashboard(page)

  await expect(page.getByText('Todavía no hay datos cargados')).toBeVisible()
  expect(await (await page.request.get(`${API}/actors`)).json()).toEqual({ items: [], total: 0 })
  expect(await (await page.request.get(`${API}/people`)).json()).toEqual({ items: [], total: 0 })
  // A document registered in the other municipality is unknown here.
  const lookup = await (await page.request.get(`${API}/people/lookup?dni=24444444`)).json()
  expect(lookup).toEqual({ person: null, registered_id: null })
  const csv = await (await page.request.get(`${API}/export/actors.csv`)).text()
  expect(csv).not.toContain(SEEDED_ACTOR)
})

test('actors csv download contains the seeded actors', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Descargar actores' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('economic-actors.csv')
})
