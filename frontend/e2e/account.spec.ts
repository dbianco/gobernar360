import { expect, test } from '@playwright/test'

import { login, PASSWORD } from './helpers.ts'

test('a user updates their contact phone only with their current password', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await page.getByRole('link', { name: 'Leo Lectura' }).click()
  const phone = page.getByLabel('Teléfono de contacto')
  await phone.fill('3472 15-123456')

  await page.getByLabel('Contraseña actual').fill('not-my-password')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText('La contraseña actual no es correcta.')).toBeVisible()
  await page.reload()
  await expect(phone).toHaveValue('')

  await phone.fill('3472 15-123456')
  await page.getByLabel('Contraseña actual').fill(PASSWORD)
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText('Guardamos los cambios.')).toBeVisible()
  await page.reload()
  await expect(phone).toHaveValue('3472 15-123456')
  // The password was left empty, so it is still the same.
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await login(page, 'lectura@noetinger.test')
})
