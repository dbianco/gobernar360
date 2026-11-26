import { expect, test } from '@playwright/test'

import { login, sidebar } from './helpers.ts'

test('everybody finds the guide in the menu, and administrators read their part of it', async ({
  page,
}) => {
  await login(page, 'lectura@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Ayuda' }).click()
  await expect(page.getByRole('heading', { name: 'Ayuda', level: 2 })).toBeVisible()
  await expect(page.getByRole('button', { name: /Primeros pasos/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Configuración/ })).toHaveCount(0)
})

test('the administrator has users and zones inside Configuración, not in the menu', async ({
  page,
}) => {
  await login(page, 'admin@noetinger.test')
  await expect(sidebar(page).getByRole('link', { name: 'Usuarios' })).toHaveCount(0)
  await expect(sidebar(page).getByRole('link', { name: 'Zonas' })).toHaveCount(0)

  await sidebar(page).getByRole('link', { name: 'Ayuda' }).click()
  await expect(page.getByRole('button', { name: /^Configuración/ })).toBeVisible()

  // The old addresses lead to the tabs.
  await page.goto('/admin/users')
  await expect(page.getByRole('tab', { name: 'Usuarios', selected: true })).toBeVisible()
  await page.goto('/admin/zones')
  await expect(page.getByRole('tab', { name: 'Mapas y zonas', selected: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Tipo de mapa' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Zonas', level: 2 })).toBeVisible()
})
