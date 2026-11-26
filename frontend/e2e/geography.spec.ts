import { expect, type Page, type Request, test } from '@playwright/test'

import { login, logout, openZones, sidebar } from './helpers.ts'

const API = '/api/dashboards'
// A street of the demo that crosses Centro and Norte.
const STREET = 'Pavimentación de la calle San Martín'
const PLAZA = 'Renovación de la plaza central'

// The tests run offline: without its background the map must work the same.
const TILES = /openstreetmap\.(org|de|fr)\/|opentopomap\.org|memomaps\.de|thunderforest\.com/
test.beforeEach(({ page }) => page.route(TILES, (route) => route.abort()))

async function open(page: Page, dashboard: string, tabName?: string) {
  await sidebar(page).getByRole('link', { name: dashboard }).click()
  await expect(page.getByRole('heading', { name: dashboard, level: 2 })).toBeVisible()
  if (tabName) await page.getByRole('tab', { name: tabName, exact: true }).click()
}

const map = (page: Page, name: string) => page.getByRole('region', { name })
const mark = (page: Page, name: string | RegExp) => page.getByRole('button', { name })

/** The row of a zone in the breakdown of a summary. */
const zoneRow = (page: Page, title: string, zone: string) =>
  page.getByRole('table', { name: title }).getByRole('row', { name: new RegExp(`^${zone}`) })

/** Areas the map asked for, in order. */
function watchAreas(page: Page): { bbox: number[]; zoom: number }[] {
  const areas: { bbox: number[]; zoom: number }[] = []
  page.on('request', (request: Request) => {
    const url = new URL(request.url())
    if (!url.pathname.endsWith('/features')) return
    areas.push({
      bbox: url.searchParams.get('bbox')!.split(',').map(Number),
      zoom: Number(url.searchParams.get('zoom')),
    })
  })
  return areas
}

test('a member opens the map, filters it and opens a record from it', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await open(page, 'Económico', 'Mapa')
  await expect(map(page, 'Mapa de actores económicos')).toBeVisible()
  await expect(page.getByText('11 registros en el área visible.')).toBeVisible()
  // Zones and records are there although the background is not.
  await expect(page.getByText('No se pudo cargar el fondo del mapa.', { exact: false })).toBeVisible()
  await expect(map(page, 'Mapa de actores económicos').getByText('Centro')).toBeVisible()

  await page.getByRole('combobox', { name: 'Sector' }).selectOption({ label: 'Metalmecánica' })
  await expect(page.getByText('2 registros en el área visible.')).toBeVisible()
  await page.getByRole('searchbox', { name: 'Buscar' }).first().fill('tornería')
  await expect(page.getByText('1 registro en el área visible.')).toBeVisible()
  await mark(page, 'Tornería Giménez').click()
  await page.getByRole('link', { name: 'Tornería Giménez' }).click()

  await expect(page.getByRole('heading', { name: 'Tornería Giménez' })).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Ubicación', exact: true }).getByText('Parque industrial').first(),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cambiar ubicación' })).toHaveCount(0)
})

test('points cluster and separate, and panning loads only the visible area', async ({ page }) => {
  const areas = watchAreas(page)
  await login(page, 'lectura@noetinger.test')
  await open(page, 'Económico', 'Mapa')
  const frame = map(page, 'Mapa de actores económicos')
  await expect(page.getByText('11 registros en el área visible.')).toBeVisible()

  // Out, until they are all one cluster.
  const everything = mark(page, /^11 registros juntos/)
  for (let step = 0; step < 8 && !(await everything.isVisible()); step += 1) {
    await page.getByRole('button', { name: 'Alejar' }).click()
    await page.waitForTimeout(400)
  }
  await expect(everything).toBeVisible()

  // In, until each is on its own.
  await everything.click()
  await expect(everything).toHaveCount(0)
  await expect.poll(() => areas[areas.length - 1].zoom).toBeGreaterThan(12)
  await expect(mark(page, 'Dulces del Monte')).toBeVisible()

  // Every request asked for no more than the frame shows, and panning asks for another area.
  const before = areas[areas.length - 1]
  const box = (await frame.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 60)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 - 500, box.y + box.height - 60, { steps: 8 })
  await page.mouse.up()
  await expect.poll(() => areas[areas.length - 1].bbox[0]).toBeGreaterThan(before.bbox[0])
  const after = areas[areas.length - 1]
  expect(after.zoom).toBe(before.zoom)
  const degreesPerPixel = 360 / (256 * 2 ** after.zoom)
  expect(after.bbox[2] - after.bbox[0]).toBeCloseTo(box.width * degreesPerPixel, 3)
})

test('a new zone takes the projects inside it, which is in the summary', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openZones(page)
  await page.getByRole('button', { name: 'Dibujar zona' }).click()
  await page.getByRole('textbox', { name: 'Nombre' }).fill('Casco E2E')
  const frame = map(page, 'Mapa para dibujar la zona')
  await expect(frame.getByText('Centro')).toBeVisible()
  // Around the label of Centro, which the plaza is next to.
  const box = (await frame.boundingBox())!
  const label = (await frame.getByText('Centro').boundingBox())!
  const [x, y] = [label.x + label.width / 2 - box.x, label.y + label.height / 2 - box.y]
  for (const [dx, dy] of [[-30, -30], [30, -30], [30, 30], [-30, 30]]) {
    await frame.click({ position: { x: x + dx, y: y + dy } })
  }
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()

  await expect(page.getByText('Zona Casco E2E guardada.')).toBeVisible()
  // It lies inside another zone, which is reported and not forbidden.
  await expect(page.getByText('Hay zonas que se superponen')).toBeVisible()
  await expect(page.getByText(/^Casco E2E y Centro: /)).toBeVisible()

  await open(page, 'Proyectos')
  await expect(zoneRow(page, 'Proyectos por zona', 'Casco E2E')).toContainText(/[1-9]/)
  await page.getByRole('tab', { name: 'Proyectos', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('plaza')
  await expect(page.getByRole('row', { name: new RegExp(PLAZA) })).toContainText('Casco E2E, Centro')

  await openZones(page)
  await page.getByRole('button', { name: 'Dar de baja Casco E2E' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Dar de baja' }).click()
  await expect(page.getByText('Zona Casco E2E dada de baja.')).toBeVisible()
  await expect(page.getByText('Hay zonas que se superponen')).toHaveCount(0)
})

test('a boundary that crosses itself is explained and not saved', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openZones(page)
  await page.getByRole('button', { name: 'Dibujar zona' }).click()
  await page.getByRole('textbox', { name: 'Nombre' }).fill('Moño E2E')
  await page
    .getByRole('textbox', { name: 'Esquinas' })
    .fill('-32.40, -62.40\n-32.39, -62.39\n-32.39, -62.40\n-32.40, -62.39')
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()

  await expect(page.getByText('se cruza consigo mismo', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar' }).click()
  await expect(page.getByRole('row', { name: /Moño E2E/ })).toHaveCount(0)
})

test('zones are imported from a GeoJSON file', async ({ page }) => {
  const ring = [[-62.40, -32.30], [-62.39, -32.30], [-62.39, -32.29], [-62.40, -32.29], [-62.40, -32.30]]
  const geojson = {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: { nombre: 'Loteo E2E' }, geometry: { type: 'Polygon', coordinates: [ring] } },
    ],
  }
  await login(page, 'admin@noetinger.test')
  await openZones(page)
  await page.getByRole('button', { name: 'Importar GeoJSON' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'zonas.geojson',
    mimeType: 'application/geo+json',
    buffer: Buffer.from(JSON.stringify(geojson)),
  })
  await dialog.getByRole('button', { name: 'Importar' }).click()

  await expect(page.getByText('Zonas creadas: 1.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Dar de baja Loteo E2E' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Dar de baja' }).click()
  await expect(page.getByText('Zona Loteo E2E dada de baja.')).toBeVisible()
})

test('a project moved outside every zone is listed for review', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await open(page, 'Proyectos', 'Mapa')
  const review = page.getByRole('region', { name: 'Proyectos sin zona' })
  await expect(review.getByRole('link', { name: 'Planta de tratamiento de residuos' })).toBeVisible()
  await expect(review.getByRole('link', { name: STREET })).toHaveCount(0)

  await page.getByRole('tab', { name: 'Proyectos', exact: true }).click()
  await page.getByRole('link', { name: STREET }).click()
  const location = page.getByRole('region', { name: 'Ubicación', exact: true })
  // A line, so it is in both of the zones it crosses.
  await expect(location.getByText('Centro').first()).toBeVisible()
  await expect(location.getByText('Norte').first()).toBeVisible()
  await location.getByRole('button', { name: 'Cambiar ubicación' }).click()
  // The segmented control hides its radio behind the label.
  await location.getByText('Punto', { exact: true }).click()
  await location.getByRole('textbox', { name: 'Coordenadas' }).fill('-32.4200, -62.4000')
  await location.getByRole('button', { name: 'Guardar' }).click()
  await expect(location.getByText('Fuera de todas las zonas')).toBeVisible()

  await page.getByRole('tab', { name: 'Mapa', exact: true }).click()
  await review.getByRole('link', { name: STREET }).click()

  // Back to where it was, drawn again point by point.
  await location.getByRole('button', { name: 'Cambiar ubicación' }).click()
  await location.getByText('Tramo', { exact: true }).click()
  await location
    .getByRole('textbox', { name: 'Puntos del tramo' })
    .fill('-32.369, -62.311\n-32.352, -62.311')
  await location.getByRole('button', { name: 'Guardar' }).click()
  await expect(location.getByText('Norte').first()).toBeVisible()
})

test('a location is set by clicking on the map', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await open(page, 'Económico', 'Actores')
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('vivero')
  await page.getByRole('link', { name: 'Vivero El Ceibo' }).click()
  const location = page.getByRole('region', { name: 'Ubicación', exact: true })
  await location.getByRole('button', { name: 'Ubicar en el mapa' }).click()
  const frame = map(page, 'Mapa de la ubicación')
  const label = (await frame.getByText('Oeste').boundingBox())!
  const box = (await frame.boundingBox())!
  await frame.click({
    position: { x: label.x - box.x + label.width / 2, y: label.y - box.y + label.height + 12 },
  })
  await expect(location.getByRole('textbox', { name: 'Coordenadas' })).toHaveValue(/^-32\.\d+, -62\.\d+$/)
  await location.getByRole('button', { name: 'Guardar' }).click()

  await expect(location.getByRole('button', { name: 'Quitar ubicación' })).toBeVisible()
  await expect(location.getByText('Oeste').first()).toBeVisible()
  await location.getByRole('button', { name: 'Quitar ubicación' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Quitar ubicación' }).click()
  await expect(location.getByText('Todavía no tiene ubicación en el mapa.')).toBeVisible()
})

test('a viewer of Social gets zones with counts and no household', async ({ page }) => {
  const answers: string[] = []
  const asked: string[] = []
  page.on('response', async (response) => {
    const { pathname } = new URL(response.url())
    if (!pathname.startsWith(`${API}/social`)) return
    asked.push(pathname)
    answers.push(await response.text().catch(() => ''))
  })
  await login(page, 'lectura@noetinger.test')
  await open(page, 'Social', 'Mapa')

  await expect(page.getByText('es un dato sensible', { exact: false })).toBeVisible()
  await expect(zoneRow(page, 'Grupos familiares por zona', 'Sur')).toContainText('7')
  await expect(zoneRow(page, 'Grupos familiares por zona', 'Oeste')).toContainText('Reservado')
  await expect(page.locator('.leaflet-marker-icon')).toHaveCount(0)
  await open(page, 'Social', 'Grupos familiares')
  await page.getByRole('link', { name: 'Familia Moyano' }).click()
  await expect(page.getByRole('heading', { name: 'Familia Moyano' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Ubicación', exact: true })).toHaveCount(0)
  expect(asked.some((path) => /features|unzoned|location/.test(path))).toBe(false)
  expect(answers.join()).not.toMatch(/coordinates|-62\.|-32\./)

  // Nor by asking for it.
  const query = 'bbox=-180,-90,180,90&zoom=18'
  const features = await page.request.get(`${API}/social/geo/households/features?${query}`)
  expect(await features.json()).toMatchObject({ restricted: true, features: [], clusters: [] })
  expect((await page.request.get(`${API}/social/geo/households/unzoned`)).status()).toBe(403)
  const csv = await (await page.request.get(`${API}/social/export/households.csv`)).text()
  expect(csv).toContain('Familia Moyano')
  expect(csv).not.toMatch(/latitude|-62\./)

  await logout(page)
  await login(page, 'carga@noetinger.test')
  await open(page, 'Social', 'Mapa')
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
})

test('the zone profile of the overview combines the dashboards', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  const profile = page.getByRole('region', { name: 'Perfil de zona' })
  await profile.getByRole('combobox', { name: 'Zona' }).selectOption({ label: 'Centro' })

  for (const dashboard of ['Económico', 'Proyectos', 'Social']) {
    await expect(profile.getByRole('region', { name: dashboard })).toBeVisible()
  }
  await expect(profile.getByRole('region', { name: 'Social' })).toContainText('Reservado')
  await expect(profile.getByRole('region', { name: 'Ambiental' })).toHaveCount(0)
})

test('figures of a past year keep the boundaries of that year', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await open(page, 'Económico')
  await expect(page.getByText('Con los límites actuales de las zonas.')).toBeVisible()
  const lastYear = new Date().getFullYear() - 1
  await page.getByRole('combobox', { name: 'Año' }).selectOption(String(lastYear))

  await expect(
    page.getByText(`Con los límites que tenían las zonas al 31/12/${lastYear}.`),
  ).toBeVisible()
})

test('the second municipality sees no zone and no place of the first', async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')
  await openZones(page)
  await expect(page.getByText('Todavía no hay zonas.', { exact: false })).toBeVisible()
  expect(await (await page.request.get('/api/zones')).json()).toEqual([])

  for (const kind of ['projects/geo/projects', 'economic/geo/actors', 'social/geo/households']) {
    const found = await page.request.get(`${API}/${kind}/features?bbox=-180,-90,180,90&zoom=3`)
    expect(await found.json()).toMatchObject({ total: 0, features: [], clusters: [] })
  }
  await open(page, 'Económico', 'Mapa')
  await expect(page.getByText('0 registros en el área visible.')).toBeVisible()
})

test('the administrator chooses the background of the maps for everybody', async ({ page }) => {
  const asked: string[] = []
  page.on('request', (request) => TILES.test(request.url()) && asked.push(request.url()))
  const save = page.getByRole('button', { name: 'Guardar mapas y zonas' })
  const background = page.getByRole('combobox', { name: 'Fondo de los mapas' })
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Configuración' }).click()
  await page.getByRole('tab', { name: 'Mapas y zonas' }).click()
  await background.selectOption({ label: 'Mapa ciclista (Thunderforest)' })
  await expect(save).toBeDisabled()
  await background.selectOption({ label: 'Topográfico (OpenTopoMap)' })
  await expect.poll(() => asked.some((url) => url.includes('opentopomap.org'))).toBe(true)
  await save.click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()

  await logout(page)
  asked.length = 0
  await login(page, 'lectura@noetinger.test')
  await open(page, 'Económico', 'Mapa')
  await expect(page.getByRole('link', { name: 'OpenTopoMap' })).toBeVisible()
  await expect.poll(() => asked.length).toBeGreaterThan(0)
  expect(asked.every((url) => url.includes('opentopomap.org'))).toBe(true)

  await logout(page)
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Configuración' }).click()
  await page.getByRole('tab', { name: 'Mapas y zonas' }).click()
  await background.selectOption({ label: 'Estándar' })
  await save.click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()
})

test('the administrator sets how small a count is shown to viewers', async ({ page }) => {
  const threshold = page.getByRole('textbox', { name: 'Cantidad mínima para mostrar una zona' })
  const set = async (value: string) => {
    await login(page, 'admin@noetinger.test')
    await sidebar(page).getByRole('link', { name: 'Configuración' }).click()
  await page.getByRole('tab', { name: 'Mapas y zonas' }).click()
    await threshold.fill(value)
    await page.getByRole('button', { name: 'Guardar mapas y zonas' }).click()
    await expect(page.getByText('Cambios guardados.')).toBeVisible()
    await logout(page)
  }
  const sur = () => zoneRow(page, 'Grupos familiares por zona', 'Sur').getByRole('cell').nth(1)

  await set('8')
  await login(page, 'lectura@noetinger.test')
  await open(page, 'Social', 'Mapa')
  await expect(sur()).toHaveText('Reservado')
  await logout(page)
  await set('5')
  await login(page, 'lectura@noetinger.test')
  await open(page, 'Social', 'Mapa')
  await expect(sur()).toHaveText('7')
})
