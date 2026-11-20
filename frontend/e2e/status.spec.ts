import { expect, type Page, test } from '@playwright/test'

import { login, sidebar } from './helpers.ts'

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
const THIS_MONTH = MONTHS[new Date().getMonth()]

const strip = (page: Page) => page.getByRole('region', { name: 'Estado mensual' })
const lightCard = (page: Page, dashboard: string) =>
  page.getByRole('region', { name: 'Estado de los tableros' }).getByRole('group', {
    name: dashboard,
  })

async function openEnvironment(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Ambiental' }).click()
  await expect(strip(page)).toBeVisible()
}

test('admin changes this month and the overview shows it', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  // The demo leaves the current month of Ambiental in order.
  await expect(lightCard(page, 'Ambiental')).toContainText('En orden')
  await openEnvironment(page)

  await strip(page).getByRole('button', { name: `${THIS_MONTH}: En orden` }).click()
  await page.getByRole('menuitem', { name: 'Crítico' }).click()
  await expect(strip(page).getByRole('button', { name: `${THIS_MONTH}: Crítico` })).toBeVisible()

  await sidebar(page).getByRole('link', { name: 'Resumen general' }).click()
  const card = lightCard(page, 'Ambiental')
  await expect(card).toContainText('Crítico')
  await expect(card).toContainText(`${THIS_MONTH} ${new Date().getFullYear()}`)
  // The five months before it are shown small.
  await expect(card.getByRole('img')).toHaveCount(5)
})

test('viewer sees the lights but cannot change them', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await expect(lightCard(page, 'Proyectos')).toBeVisible()
  await openEnvironment(page)

  await expect(strip(page).getByRole('img', { name: `${THIS_MONTH}: Crítico` })).toBeVisible()
  await expect(strip(page).getByRole('button')).toHaveCount(0)
})

test('a member only sees the lights of the dashboards granted to them', async ({ page }) => {
  // An earlier spec gave this member the projects dashboard and nothing else.
  await login(page, 'sinacceso@noetinger.test')

  const lights = page.getByRole('region', { name: 'Estado de los tableros' })
  await expect(lights.getByRole('group', { name: 'Proyectos' })).toBeVisible()
  await expect(lights.getByRole('group')).toHaveCount(1)
  const response = await page.request.get('/api/dashboards/environment/status?year=2025')
  expect(response.status()).toBe(403)
})

test('another municipality does not see these lights', async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')

  await expect(lightCard(page, 'Ambiental')).toContainText('Sin estado')
})

test('a column header explains itself', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openEnvironment(page)

  await page.getByRole('button', { name: 'Qué significa Subcategoría' }).first().hover()

  await expect(page.getByRole('tooltip')).toContainText('División de la categoría')
})

test('a collapsed overview section stays collapsed after reloading', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  const toggle = page.getByRole('button', { name: 'Económico', exact: true })
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('Actores económicos')).toBeVisible()

  await toggle.click()
  await page.reload()

  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByText('Actores económicos')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Social', exact: true })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
})
