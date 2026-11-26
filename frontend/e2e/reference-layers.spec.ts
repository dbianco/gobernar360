import path from 'node:path'

import { expect, type Page, test } from '@playwright/test'

import { backendCommand, login, logout, sidebar } from './helpers.ts'

const SAMPLES = path.resolve(import.meta.dirname, '../../docs/idecor/samples')
const HOSPITAL = 'Salud: HOSPITAL MUNICIPAL DE NOETINGER'

// The tests run offline: the satellite image never arrives and the map must work the same.
const SATELLITE = /geotematico01\.conae\.gov\.ar/
const TILES = /openstreetmap\.org\/|geotematico01\.conae\.gov\.ar/
test.beforeEach(({ page }) => page.route(TILES, (route) => route.abort()))

const importOfficial = (...args: string[]) =>
  backendCommand('import-idecor', 'noetinger', ...args, '--from-dir', SAMPLES)

const facilities = (page: Page) => page.getByRole('switch', { name: /^Equipamiento/ })

async function openMap(page: Page, dashboard: string) {
  await sidebar(page).getByRole('link', { name: dashboard, exact: true }).click()
  await expect(page.getByRole('heading', { name: dashboard, level: 2 })).toBeVisible()
  await page.getByRole('tab', { name: 'Mapa', exact: true }).click()
}

async function openMapSettings(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Configuración' }).click()
  await page.getByRole('tab', { name: 'Mapas y zonas' }).click()
}

test('any member sees the hospital and the schools on the map', async ({ page }) => {
  importOfficial('--layers', 'health,schools')
  await login(page, 'lectura@noetinger.test')
  await openMap(page, 'Proyectos')
  await expect(page.getByRole('region', { name: 'Mapa de proyectos' })).toBeVisible()
  await expect(page.getByRole('button', { name: HOSPITAL })).toHaveCount(0)

  // The switch itself is drawn by its label.
  await facilities(page).locator('xpath=..').click()

  const hospital = page.getByRole('button', { name: HOSPITAL })
  await expect(hospital).toBeVisible()
  await expect(page.getByRole('button', { name: /^Escuela: / }).first()).toBeVisible()
  await hospital.press('Enter')
  const popup = page.locator('.leaflet-popup')
  await expect(popup).toContainText('HOSPITAL MUNICIPAL DE NOETINGER')
  await expect(popup).toContainText('Dirección: INTENDENTE MARANGON Y CUPERTINO SALINAS')
  await expect(popup).toContainText('Fuente: IDECOR')
  await expect(page.getByText('Equipamiento: IDECOR')).toBeVisible()
})

test('the satellite image is chosen, and without it the map stays usable', async ({ page }) => {
  const asked: string[] = []
  page.on('request', (request) => SATELLITE.test(request.url()) && asked.push(request.url()))
  await login(page, 'admin@noetinger.test')
  await openMapSettings(page)
  await expect(page.getByRole('textbox', { name: 'Clave en IDECOR' })).toHaveValue('360124')
  await expect(page.getByRole('textbox', { name: 'Clave en IDECOR' })).not.toBeEditable()

  const background = page.getByRole('combobox', { name: 'Fondo de los mapas' })
  await background.selectOption({ label: 'Satélite (CONAE)' })
  await expect(page.getByText('un uso intenso conviene acordarlo', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Guardar mapas y zonas' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()

  await openMap(page, 'Económico')
  const map = page.getByRole('region', { name: 'Mapa de actores económicos' })
  await expect(map.getByText('Imagen: CONAE – Pleiades Neo 2023', { exact: false })).toBeVisible()
  await expect(
    page.getByText('La imagen satelital cubre solo la localidad', { exact: false }),
  ).toBeVisible()
  await expect(map.getByText('Centro', { exact: true })).toBeVisible()
  await expect(page.getByText('11 registros en el área visible.')).toBeVisible()
  // The layer of the town, and the row before the column.
  expect(asked[0]).toMatch(
    /rest\/Localidades:Cordoba_Noetinger_2023\/raster\/EPSG:900913\/EPSG:900913:\d+\/\d+\/\d+\?format=image\/png$/,
  )

  await openMapSettings(page)
  await background.selectOption({ label: 'Estándar' })
  await page.getByRole('button', { name: 'Guardar mapas y zonas' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()
})

test('the official urban radius becomes a zone with the law that approves it', async ({ page }) => {
  importOfficial('--radius')
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Zonas' }).click()

  await expect(page.getByRole('cell', { name: /^Radio urbano/ })).toContainText(
    'Límite oficial: Expte 0423-031865-2008 - Ley 10796/2022',
  )
  await expect(page.getByText('Hay zonas que se superponen')).toBeVisible()

  // Other specs count on the zones of the demo alone.
  await page.getByRole('button', { name: 'Dar de baja Radio urbano' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Dar de baja' }).click()
  await expect(page.getByText('Zona Radio urbano dada de baja.')).toBeVisible()
})

test('the operator says where a municipality is, and the other one has none of it', async ({
  page,
}) => {
  await login(page, 'operador@gobernar360.test')
  const found = await page.request.get('/api/platform/municipalities')
  const municipalities: { id: string; slug: string }[] = await found.json()
  const commune = municipalities.find(({ slug }) => slug === 'comuna-demo')!
  await page.goto(`/platform/municipalities/${commune.id}/settings/maps`)
  const key = page.getByRole('textbox', { name: 'Clave en IDECOR' })
  await key.fill('12')
  await expect(page.getByText('Tiene que tener seis números.')).toBeVisible()
  await key.fill('360200')
  await page.getByRole('button', { name: 'Guardar fuentes oficiales' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()
  await key.fill('')
  await page.getByRole('button', { name: 'Guardar fuentes oficiales' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()
  await logout(page)

  await login(page, 'admin@comuna-demo.test')
  await openMap(page, 'Proyectos')
  await expect(page.getByRole('region', { name: 'Mapa de proyectos' })).toBeVisible()
  await expect(facilities(page)).toHaveCount(0)
  expect(await (await page.request.get('/api/geo/reference-layers')).json()).toEqual([])
  await openMapSettings(page)
  await expect(page.getByRole('option', { name: 'Estándar' })).toHaveCount(1)
  await expect(page.getByRole('option', { name: 'Satélite (CONAE)' })).toHaveCount(0)
})
