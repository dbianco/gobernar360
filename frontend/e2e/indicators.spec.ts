import { expect, type Page, test } from '@playwright/test'

import { login, logout, sidebar } from './helpers.ts'

const headline = (page: Page) => page.getByRole('region', { name: 'Indicadores clave' })
const headlineCard = (page: Page, label: string) =>
  headline(page).locator('[data-indicator]').filter({ hasText: label })
const combined = (page: Page) => page.getByRole('region', { name: 'Indicadores combinados' })

async function openProjects(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Proyectos' }).click()
  await expect(headline(page)).toBeVisible()
}

async function setSofiasSocialAccess(page: Page, level: 'Lectura' | 'Sin acceso') {
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()
  const access = page.getByRole('combobox', { name: 'Social: Sofía Sin Acceso' })
  await access.selectOption({ label: level })
  await expect(access).toHaveValue(level === 'Lectura' ? 'viewer' : '')
}

test('every headline card of the projects summary shows its evolution', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openProjects(page)

  const cards = headline(page).locator('[data-indicator]')
  await expect(cards).toHaveCount(6)
  for (const card of await cards.all()) {
    await expect(card).toContainText('respecto del mes anterior')
    await expect(card.getByRole('img', { name: /en los últimos 12 meses/ })).toBeVisible()
  }
  // The month's numbers sit under each light of the status strip.
  const strip = page.getByRole('region', { name: 'Estado mensual' })
  await expect(strip.getByRole('row', { name: /Proyectos retrasados/ })).toBeVisible()

  await headline(page)
    .getByRole('button', { name: 'Ver la evolución de Proyectos retrasados' })
    .click()
  const detail = page.getByRole('dialog', { name: 'Proyectos retrasados' })
  // The series and its target line.
  await expect(detail.locator('.recharts-line')).toHaveCount(2)
  await detail.getByRole('button', { name: 'Ver como tabla' }).click()
  await expect(detail.getByRole('row')).toHaveCount(13)
  await expect(detail.getByRole('columnheader', { name: 'Meta' })).toBeVisible()
})

test('a target below the current number of delayed projects is missed', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openProjects(page)
  const delayed = headlineCard(page, 'Proyectos retrasados')
  // The demo's target is met.
  await expect(delayed).toContainText('En meta')
  const current = Number(await delayed.locator('p').nth(1).innerText())
  expect(current).toBeGreaterThan(0)

  await page.getByRole('tab', { name: 'Parámetros' }).click()
  await page.getByRole('tab', { name: 'Metas' }).click()
  const year = new Date().getFullYear()
  const row = page.getByRole('row', { name: /Proyectos retrasados/ })
  await row.getByRole('spinbutton', { name: `Meta ${year} de Proyectos retrasados` }).fill(
    String(current - 1),
  )
  await row.getByRole('button', { name: 'Guardar' }).click()
  await expect(row.getByRole('button', { name: 'Guardar' })).toBeDisabled()

  await page.getByRole('tab', { name: 'Resumen' }).click()
  await expect(delayed).toContainText('Fuera de meta')
  await expect(delayed).toContainText(`1 por encima de la meta de ${current - 1}`)
})

test('combined indicators are shown only to members who see both dashboards', async ({
  page,
}) => {
  await login(page, 'admin@noetinger.test')
  await expect(combined(page).locator('[data-indicator]')).toHaveCount(2)
  await expect(combined(page)).toContainText('Trámites en línea por actor económico')
  await expect(combined(page)).toContainText('Prestaciones sociales del año por proyecto activo')
  await setSofiasSocialAccess(page, 'Lectura')
  await logout(page)

  try {
    await login(page, 'sinacceso@noetinger.test')
    await expect(page.getByRole('heading', { name: 'Social', level: 3 })).toBeVisible()
    await expect(page.locator('[data-indicator]').first()).toBeVisible()
    await expect(combined(page)).toHaveCount(0)
    const response = await page.request.get('/api/overview/combined')
    expect(await response.json()).toEqual([])
    await logout(page)
  } finally {
    // Later specs expect this member without any dashboard.
    await login(page, 'admin@noetinger.test')
    await setSofiasSocialAccess(page, 'Sin acceso')
  }
})

test('the overview shows only the dashboards chosen next to its title', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  const lights = page.getByRole('region', { name: 'Estado de los tableros' })
  // One light per enabled dashboard; another spec may have enabled one more.
  await expect(lights.getByRole('group', { name: 'Económico' })).toBeVisible()
  const all = await lights.getByRole('group').count()
  expect(all).toBeGreaterThanOrEqual(5)

  await page.getByRole('button', { name: 'Ocultar Económico' }).click()

  await expect(lights.getByRole('group')).toHaveCount(all - 1)
  await expect(lights.getByRole('group', { name: 'Económico' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Económico', level: 3 })).toHaveCount(0)
  await expect(combined(page).locator('[data-indicator]')).toHaveCount(1)
  await expect(combined(page)).not.toContainText('actor económico')

  await page.getByRole('button', { name: 'Mostrar Económico' }).click()
  await expect(page.getByRole('heading', { name: 'Económico', level: 3 })).toBeVisible()
  await expect(combined(page).locator('[data-indicator]')).toHaveCount(2)

  // Not remembered: opening the page again shows every dashboard.
  await page.getByRole('button', { name: 'Ocultar Social' }).click()
  await page.reload()
  await expect(lights.getByRole('group')).toHaveCount(all)
})
