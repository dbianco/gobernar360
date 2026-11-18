import { expect, test } from '@playwright/test'

import { login, logout, sidebar } from './helpers.ts'

test('operator creates a municipality and enables the projects dashboard', async ({ page }) => {
  await login(page, 'operador@gobernar360.test')
  await expect(page.getByRole('heading', { name: 'Municipios de la plataforma' })).toBeVisible()

  await page.getByLabel('Nombre').fill('Villa Prueba')
  await page.getByLabel('Identificador').fill('villa-prueba')
  await page.getByRole('button', { name: 'Crear municipio' }).click()
  await expect(page.getByRole('heading', { name: 'Villa Prueba' })).toBeVisible()

  const dashboard = page.getByRole('checkbox', { name: 'Proyectos en Villa Prueba' })
  await expect(dashboard).not.toBeChecked()
  // The box reflects what the server stored, so it turns on once the change is saved.
  await dashboard.click()
  await expect(dashboard).toBeChecked()
  await page.reload()
  await expect(page.getByRole('checkbox', { name: 'Proyectos en Villa Prueba' })).toBeChecked()
})

test('member without grants does not see the projects dashboard', async ({ page }) => {
  await login(page, 'sinacceso@noetinger.test')

  await expect(page.getByText('No tenés tableros habilitados')).toBeVisible()
  await expect(sidebar(page).getByRole('link', { name: 'Proyectos' })).toHaveCount(0)

  await page.goto('/d/projects')
  await expect(page.getByText('No tenés acceso a este tablero')).toBeVisible()
})

test('admin grants a user read access and the dashboard appears for them', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()
  await page
    .getByRole('combobox', { name: 'Proyectos: Sofía Sin Acceso' })
    .selectOption({ label: 'Lectura' })
  await expect(page.getByRole('combobox', { name: 'Proyectos: Sofía Sin Acceso' })).toHaveValue(
    'viewer',
  )
  await logout(page)

  await login(page, 'sinacceso@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Proyectos' }).click()
  await expect(page.getByRole('heading', { name: 'Proyectos', level: 2 })).toBeVisible()
  await expect(page.getByText('Proyectos activos')).toBeVisible()
})
