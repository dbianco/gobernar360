import { expect, test } from '@playwright/test'

import { login, sidebar, statValue } from './helpers.ts'

const SEEDED_PROJECT = 'Pavimentación de la calle San Martín'
const API = '/api/dashboards/projects'

test('editor creates a project with a milestone and the summary updates', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Proyectos' }).click()
  const activeBefore = await statValue(page, 'Proyectos activos')

  await page.getByRole('tab', { name: 'Proyectos' }).click()
  await page.getByRole('button', { name: 'Cargar nuevo proyecto' }).click()
  const form = page.getByRole('dialog')
  await form.getByRole('textbox', { name: 'Nombre' }).fill('Proyecto E2E')
  await form.getByRole('combobox', { name: 'Eje' }).selectOption({ label: 'Ciudad segura' })
  await form.getByRole('combobox', { name: 'Dependencia' }).selectOption({ label: 'Seguridad' })
  await form.getByRole('checkbox', { name: /^ODS 16:/ }).check()
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()

  await page.getByRole('link', { name: 'Proyecto E2E' }).click()
  await expect(page.getByRole('heading', { name: 'Proyecto E2E' })).toBeVisible()
  await page.getByLabel('Hito', { exact: true }).fill('Hito E2E')
  await page.getByLabel('Fecha comprometida').fill('2030-01-15')
  await page.getByRole('button', { name: 'Agregar hito' }).click()
  await expect(page.getByRole('row', { name: /Hito E2E/ })).toContainText('15/01/2030')

  await page.getByRole('tab', { name: 'Resumen' }).click()
  await expect.poll(() => statValue(page, 'Proyectos activos')).toBe(activeBefore + 1)
})

test('viewer cannot see the create button and a direct POST is forbidden', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Proyectos' }).click()
  await page.getByRole('tab', { name: 'Proyectos' }).click()

  await expect(page.getByRole('link', { name: SEEDED_PROJECT })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cargar nuevo proyecto' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'Parámetros' })).toHaveCount(0)

  const response = await page.request.post(`${API}/projects`, {
    headers: { 'X-Requested-With': 'gobernar360' },
    data: { name: 'Should not exist' },
  })
  expect(response.status()).toBe(403)
})

test('overview shows the projects indicators', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')

  await expect(page.getByRole('heading', { name: 'Resumen general' })).toBeVisible()
  expect(await statValue(page, 'Proyectos activos')).toBeGreaterThan(0)
  expect(await statValue(page, 'Hitos en alerta')).toBeGreaterThan(0)
  await expect(page.getByText('Presupuesto ejecutado')).toBeVisible()
})

test("admin of the second municipality sees none of the first municipality's projects", async ({
  page,
}) => {
  await login(page, 'admin@comuna-demo.test')
  await sidebar(page).getByRole('link', { name: 'Proyectos' }).click()
  await page.getByRole('tab', { name: 'Proyectos' }).click()

  await expect(page.getByRole('link', { name: 'Mejorado de caminos rurales' })).toBeVisible()
  await expect(page.getByRole('link', { name: SEEDED_PROJECT })).toHaveCount(0)

  const projects = await (await page.request.get(`${API}/projects`)).json()
  expect(projects.map((project: { name: string }) => project.name).sort()).toEqual([
    'Ampliación del dispensario',
    'Mejorado de caminos rurales',
  ])
})

test('projects csv download contains the seeded projects', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Proyectos' }).click()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Descargar proyectos' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('projects.csv')

  const csv = await (await page.request.get(`${API}/export/projects.csv`)).text()
  expect(csv).toContain(SEEDED_PROJECT)
  expect(csv).not.toContain('Mejorado de caminos rurales')
})
