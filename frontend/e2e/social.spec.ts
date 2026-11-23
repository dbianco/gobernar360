import { expect, type Page, test } from '@playwright/test'

import { login, sidebar, statValue } from './helpers.ts'

const API = '/api/dashboards/social'
// Part of a description seeded for an intervention; reserved text.
const SEEDED_DESCRIPTION = 'Vivienda con filtraciones'

async function openDashboard(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Social' }).click()
  await expect(page.getByRole('heading', { name: 'Social', level: 2 })).toBeVisible()
}

const tab = (page: Page, name: string) => page.getByRole('tab', { name, exact: true })

test('editor registers a person and a household and records what was done', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  const peopleBefore = await statValue(page, 'Personas')
  const deliveriesBefore = await statValue(page, 'Prestaciones del año')
  const interventionsBefore = await statValue(page, 'Intervenciones del año')

  await tab(page, 'Personas').click()
  await page.getByRole('button', { name: 'Cargar nueva persona' }).click()
  let form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'DNI' }).fill('46.222.333')
  await form.getByRole('textbox', { name: 'Nombre', exact: true }).fill('Sara')
  await form.getByRole('textbox', { name: 'Apellido', exact: true }).fill('Ejemplo')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('ejemplo')
  await expect(page.getByRole('row', { name: /Ejemplo, Sara/ })).toContainText('46.222.333')

  await tab(page, 'Grupos familiares').click()
  await page.getByRole('button', { name: 'Cargar nuevo grupo familiar' }).click()
  form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Nombre' }).fill('Familia Ejemplo E2E')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await page.getByRole('link', { name: 'Familia Ejemplo E2E' }).click()
  await page.getByRole('button', { name: 'Agregar integrante' }).click()
  await page.getByRole('textbox', { name: 'Buscar persona' }).fill('Ejemplo')
  await page.getByRole('button', { name: 'Agregar a Ejemplo, Sara' }).click()
  // The first member of a household is offered as its head.
  await expect(page.getByRole('combobox', { name: 'Parentesco de Ejemplo, Sara' })).toHaveValue(
    'head',
  )

  await page.getByRole('link', { name: 'Ejemplo, Sara' }).first().click()
  await expect(page.getByRole('heading', { name: 'Ejemplo, Sara' })).toBeVisible()
  await page.getByRole('button', { name: 'Registrar prestación' }).click()
  form = page.getByRole('dialog')
  await form.getByRole('combobox', { name: 'Prestación' }).selectOption({
    label: 'Módulo alimentario (Alimentos)',
  })
  await form.getByRole('spinbutton', { name: 'Cantidad' }).fill('2')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Módulo alimentario/ })).toBeVisible()

  await page.getByRole('button', { name: 'Registrar intervención' }).click()
  form = page.getByRole('dialog')
  await form.getByRole('combobox', { name: 'Tipo' }).selectOption({ label: 'Visita a domicilio' })
  await expect(form.getByRole('textbox', { name: 'Realizada por' })).toHaveValue('Carla Carga')
  await form.getByRole('textbox', { name: 'Descripción' }).fill('Nota reservada E2E')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Visita a domicilio/ })).toContainText(
    'Nota reservada E2E',
  )

  await tab(page, 'Resumen').click()
  await expect.poll(() => statValue(page, 'Prestaciones del año')).toBe(deliveriesBefore + 1)
  expect(await statValue(page, 'Intervenciones del año')).toBe(interventionsBefore + 1)
  expect(await statValue(page, 'Personas')).toBe(peopleBefore + 1)
})

test('a person the economic dashboard loaded is offered, not typed again', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  await tab(page, 'Personas').click()
  // Rosa Aguirre is in the economic dashboard only: invisible here until incorporated.
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('aguirre')
  await expect(page.getByText('No hay personas que coincidan.')).toBeVisible()

  await page.getByRole('button', { name: 'Cargar nueva persona' }).click()
  const form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'DNI' }).fill('24444444')
  await form.getByRole('textbox', { name: 'Teléfono' }).click()

  await expect(form.getByText(/Aguirre, Rosa ya está en el padrón del municipio/)).toBeVisible()
  await expect(form.getByRole('textbox', { name: 'Nombre', exact: true })).toHaveValue('Rosa')
})

test('viewer reads the dashboard without the reserved text and cannot load data', async ({
  page,
}) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  await expect(page.getByRole('tab', { name: 'Parámetros' })).toHaveCount(0)
  await tab(page, 'Intervenciones').click()
  await expect(page.getByRole('row', { name: /Visita a domicilio/ }).first()).toContainText(
    'Reservado',
  )
  await expect(page.getByText(SEEDED_DESCRIPTION)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Registrar intervención' })).toHaveCount(0)
  await tab(page, 'Personas').click()
  await expect(page.getByRole('button', { name: 'Cargar nueva persona' })).toHaveCount(0)
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('sosa')
  await page.getByRole('link', { name: 'Sosa, Diego' }).click()
  await expect(page.getByRole('heading', { name: 'Sosa, Diego' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Familia Sosa' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Registrar prestación' })).toHaveCount(0)
  await expect(page.getByText(SEEDED_DESCRIPTION)).toHaveCount(0)
  await tab(page, 'Reportes').click()
  await expect(page.getByRole('heading', { name: 'Personas por barrio' })).toBeVisible()

  // The server withholds the text; hiding it is not left to the screen.
  const listed = await (await page.request.get(`${API}/interventions?limit=200`)).json()
  expect(listed.total).toBeGreaterThan(0)
  expect(listed.items.every((item: { description: unknown }) => item.description === null)).toBe(
    true,
  )
  const csv = await (await page.request.get(`${API}/export/interventions.csv`)).text()
  expect(csv).toContain('performed_by')
  expect(csv).not.toContain('description')
  expect(csv).not.toContain(SEEDED_DESCRIPTION)
  const headers = { 'X-Requested-With': 'gobernar360' }
  const created = await page.request.post(`${API}/households`, { headers, data: { name: 'x' } })
  expect(created.status()).toBe(403)
  const lookup = await page.request.get(`${API}/people/lookup?dni=36987654`)
  expect(lookup.status()).toBe(403)
})

test('dashboard admin adds a benefit and it can then be delivered', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)
  await tab(page, 'Parámetros').click()

  await page.getByRole('button', { name: 'Agregar prestación' }).click()
  let form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Nombre' }).fill('Garrafa social E2E')
  await form.getByRole('combobox', { name: 'Categoría' }).selectOption({ label: 'Hábitat' })
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Garrafa social E2E/ })).toContainText('Hábitat')

  await tab(page, 'Prestaciones').click()
  await page.getByRole('button', { name: 'Registrar prestación' }).click()
  form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Buscar persona' }).fill('quiroga pedro')
  await form.getByRole('button', { name: 'Elegir a Quiroga, Pedro' }).click()
  await form.getByRole('combobox', { name: 'Prestación' }).selectOption({
    label: 'Garrafa social E2E (Hábitat)',
  })
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Garrafa social E2E/ })).toContainText(
    'Quiroga, Pedro',
  )
})

test('overview shows the social indicators', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')

  await expect(page.getByRole('heading', { name: 'Resumen general' })).toBeVisible()
  expect(await statValue(page, 'Personas asistidas')).toBeGreaterThan(0)
  expect(await statValue(page, 'Grupos familiares')).toBeGreaterThan(0)
  expect(await statValue(page, 'Intervenciones del año')).toBeGreaterThan(0)
})

test("the second municipality sees none of the first municipality's social records", async ({
  page,
}) => {
  await login(page, 'admin@comuna-demo.test')
  await openDashboard(page)

  await expect(page.getByText('Todavía no hay datos cargados')).toBeVisible()
  const empty = { items: [], total: 0 }
  for (const list of ['people', 'households', 'deliveries', 'interventions']) {
    expect(await (await page.request.get(`${API}/${list}`)).json()).toEqual(empty)
  }
  // A document registered in the other municipality is unknown here.
  const lookup = await (await page.request.get(`${API}/people/lookup?dni=36987654`)).json()
  expect(lookup).toEqual({ person: null, registered_id: null })
  const csv = await (await page.request.get(`${API}/export/interventions.csv`)).text()
  expect(csv).not.toContain(SEEDED_DESCRIPTION)
})

test('people csv download is offered from the summary', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Descargar personas' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('social-people.csv')
})
