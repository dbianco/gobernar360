import { type Browser, expect, type Page, test } from '@playwright/test'

import { login, sidebar } from './helpers.ts'

// Choices are saved on the server first and then shown, so they are clicked, not checked.
const MONTHS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]  // prettier-ignore
const now = new Date()
const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
const LAST = `${MONTHS[lastMonth.getMonth()]} ${lastMonth.getFullYear()}`
const CSRF = { 'X-Requested-With': 'gobernar360' }
// People of the demo registry (economic and social dashboards) and their documents.
const REGISTRY = ['Diego Sosa', 'Rosa Aguirre', 'Elena Paz', 'Norma Moyano', '36987654', '30222111']

async function openReports(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Informes' }).click()
  await expect(page.getByRole('heading', { name: 'Informes mensuales' })).toBeVisible()
}

async function downloadLastMonth(page: Page): Promise<Buffer> {
  const link = page.getByRole('link', { name: `Descargar el informe de ${LAST}` })
  const response = await page.request.get((await link.getAttribute('href')) as string)
  expect(response.headers()['content-type']).toBe('application/pdf')
  return await response.body()
}

/** A page in a fresh browser context: no cookies, no session. */
async function anonymousPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext()
  expect(await context.cookies()).toEqual([])
  return await context.newPage()
}

test('a closed month gives the same document after its data changes', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openReports(page)

  await page.getByRole('button', { name: `Cerrar ${LAST}` }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Comentario sobre Proyectos').fill('Un mes con lluvias en las obras.')
  await dialog.getByRole('button', { name: 'Cerrar y congelar' }).click()
  await expect(page.getByText(`Se cerró ${LAST}.`)).toBeVisible()
  const before = await downloadLastMonth(page)
  expect(before.subarray(0, 5).toString()).toBe('%PDF-')

  // A project's progress changes afterwards.
  const terms = await (await page.request.get('/api/dashboards/projects/terms')).json()
  const projects = await (
    await page.request.get(`/api/dashboards/projects/projects?term_id=${terms[0].id}`)
  ).json()
  const portal = projects.find((p: { name: string }) => p.name === 'Portal de datos abiertos')
  const changed = await page.request.patch(`/api/dashboards/projects/projects/${portal.id}`, {
    headers: CSRF,
    data: { manual_progress: portal.manual_progress + 50 },
  })
  expect(changed.status()).toBe(200)

  const after = await downloadLastMonth(page)
  expect(after.equals(before)).toBe(true)
})

test('the public page shows exactly what was published, to anyone', async ({ page, browser }) => {
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Página pública' }).click()
  await page.getByRole('checkbox', { name: 'Publicar Proyectos retrasados' }).click()
  await expect(page.getByRole('checkbox', { name: 'Publicar Proyectos retrasados' })).toBeChecked()
  await page.getByRole('checkbox', { name: 'Publicar Prestaciones del año' }).click()
  await expect(page.getByRole('checkbox', { name: 'Publicar Prestaciones del año' })).toBeChecked()
  await openReports(page)
  await page.getByRole('button', { name: `Publicar el informe de ${LAST}` }).click()
  await expect(page.getByRole('button', { name: `Dejar de publicar el informe de ${LAST}` }))
    .toBeVisible()

  const visitor = await anonymousPage(browser)
  await visitor.goto('/p/noetinger')
  await expect(visitor.getByRole('heading', { name: 'Noetinger', level: 1 })).toBeVisible()
  const cards = visitor.locator('[data-indicator]')
  await expect(cards).toHaveCount(2)
  await expect(cards.nth(0)).toContainText('Proyectos retrasados')
  await expect(cards.nth(1)).toContainText('Prestaciones del año')
  const reports = visitor.getByRole('region', { name: 'Informes mensuales' })
  await expect(reports.getByRole('link', { name: 'Descargar PDF' })).toHaveCount(1)
  await expect(reports).toContainText(`Informe de ${LAST.toLowerCase()}`)
  const published = await visitor.request.get(
    (await reports.getByRole('link', { name: 'Descargar PDF' }).getAttribute('href')) as string,
  )
  expect(published.headers()['content-type']).toBe('application/pdf')

  // Not published, or not a public page: not found.
  expect((await visitor.request.get('/api/public/noetinger/indicators/projects.active')).status())
    .toBe(404)
  expect((await visitor.request.get('/api/public/comuna-demo')).status()).toBe(404)
  await visitor.goto('/p/comuna-demo')
  await expect(visitor.getByRole('heading', { name: 'Esta página no existe' })).toBeVisible()

  // Unpublishing takes effect at once.
  await sidebar(page).getByRole('link', { name: 'Página pública' }).click()
  await page.getByRole('checkbox', { name: 'Publicar Prestaciones del año' }).click()
  await expect(page.getByRole('checkbox', { name: 'Publicar Prestaciones del año' }))
    .not.toBeChecked()
  await visitor.goto('/p/noetinger')
  await expect(visitor.locator('[data-indicator]')).toHaveCount(1)
  await expect(visitor.getByText('Prestaciones del año')).toHaveCount(0)

  // Nobody of the people registry appears.
  const pageText = await visitor.locator('body').innerText()
  const api = await (await visitor.request.get('/api/public/noetinger')).text()
  for (const mention of REGISTRY) {
    expect(pageText).not.toContain(mention)
    expect(api).not.toContain(mention)
  }
  await visitor.context().close()
})
