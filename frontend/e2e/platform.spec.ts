import { expect, test } from '@playwright/test'

import { login, logout, PASSWORD, sidebar } from './helpers.ts'

test('operator creates a municipality, configures it and its administrator signs in', async ({
  page,
}) => {
  await login(page, 'operador@gobernar360.test')
  await expect(page.getByRole('heading', { name: 'Municipios de la plataforma' })).toBeVisible()

  await page.getByLabel('Nombre').fill('Villa Prueba')
  await page.getByLabel('Identificador').fill('villa-prueba')
  await page.getByRole('button', { name: 'Crear municipio' }).click()
  await page.getByRole('link', { name: 'Configurar Villa Prueba' }).click()
  await expect(page.getByRole('heading', { name: 'Villa Prueba', level: 2 })).toBeVisible()

  await page.getByLabel('Nombre', { exact: true }).fill('Villa Prueba Norte')
  await page.getByRole('button', { name: 'Guardar datos' }).click()
  await expect(page.getByRole('heading', { name: 'Villa Prueba Norte', level: 2 })).toBeVisible()

  const dashboard = page.getByRole('checkbox', { name: 'Proyectos' })
  await expect(dashboard).not.toBeChecked()
  // The box reflects what the server stored, so it turns on once the change is saved.
  await dashboard.click()
  await expect(dashboard).toBeChecked()
  await page.reload()
  await expect(page.getByRole('checkbox', { name: 'Proyectos' })).toBeChecked()

  await page.getByRole('button', { name: 'Agregar usuario' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Nombre y apellido').fill('Vera Intendenta')
  await form.getByLabel('Email').fill('admin@villa-prueba.test')
  await form.getByLabel('Contraseña inicial').fill('clave-de-vera-123')
  await form.getByRole('checkbox', { name: 'Administrador del municipio' }).check()
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /Vera Intendenta/ })).toBeVisible()
  await logout(page)

  await login(page, 'admin@villa-prueba.test', 'clave-de-vera-123')
  await expect(page.getByRole('banner').getByText('Villa Prueba Norte')).toBeVisible()
  await expect(sidebar(page).getByRole('link', { name: 'Proyectos' })).toBeVisible()
  await expect(sidebar(page).getByRole('link', { name: 'Plataforma' })).toHaveCount(0)
  // A municipality administrator has no way into another municipality's configuration.
  const response = await page.request.get('/api/platform/municipalities')
  expect(response.status()).toBe(403)
})

test('operator sets a new password for a municipality user', async ({ page }) => {
  await login(page, 'operador@gobernar360.test')
  await page.getByRole('link', { name: 'Configurar Noetinger' }).click()

  await page.getByRole('button', { name: 'Cambiar contraseña de Sofía Sin Acceso' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Contraseña nueva').fill('otra-clave-456789')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Contraseña cambiada: Sofía Sin Acceso')).toBeVisible()
  await logout(page)

  await page.getByLabel('Email').fill('sinacceso@noetinger.test')
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.getByText('El email o la contraseña no son correctos.')).toBeVisible()
  await login(page, 'sinacceso@noetinger.test', 'otra-clave-456789')
  await logout(page)

  // Other tests sign in with the demo password: put it back.
  await login(page, 'operador@gobernar360.test')
  const municipalities = await (await page.request.get('/api/platform/municipalities')).json()
  const noetinger = municipalities.find((item: { slug: string }) => item.slug === 'noetinger')
  const users = await (
    await page.request.get(`/api/platform/municipalities/${noetinger.id}/users`)
  ).json()
  const sofia = users.find(
    (item: { user: { email: string } }) => item.user.email === 'sinacceso@noetinger.test',
  )
  const restored = await page.request.put(
    `/api/platform/municipalities/${noetinger.id}/users/${sofia.membership_id}/password`,
    { headers: { 'X-Requested-With': 'gobernar360' }, data: { password: PASSWORD } },
  )
  expect(restored.status()).toBe(204)
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
  await expect(
    page.getByRole('region', { name: 'Indicadores clave' }).getByText('Proyectos activos'),
  ).toBeVisible()
})
