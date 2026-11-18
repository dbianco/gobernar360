import { expect, type Page } from '@playwright/test'

export const PASSWORD = 'gobernar360-demo'

export async function login(page: Page, email: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()
}

export async function logout(page: Page) {
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Ingresar a gobernar360' })).toBeVisible()
}

export const sidebar = (page: Page) => page.getByRole('navigation')

/** The number shown in a headline card, found by its label. */
export async function statValue(page: Page, label: string): Promise<number> {
  const card = page.locator('[data-indicator]').filter({ hasText: label }).first()
  await expect(card).toBeVisible()
  const text = await card.locator('p').nth(1).innerText()
  return Number(text.replace(/[^\d-]/g, ''))
}
