import { expect, test } from '@playwright/test'

import {
  backendCommand,
  configureNoetinger,
  emailsTo,
  login,
  logout,
  sidebar,
  theEmailTo,
} from './helpers.ts'

// Configuración: each municipality's recipients, single sign-on and email texts.

async function openSettings(page: import('@playwright/test').Page) {
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()
  await page.getByRole('tab', { name: 'Configuración' }).click()
  await expect(page.getByRole('heading', { name: 'Configuración', level: 2 })).toBeVisible()
}

test('the next invitation uses the text the administrator wrote', async ({ page, request }) => {
  test.slow()
  const since = new Date()
  const email = `texto-${Date.now()}@noetinger.test`
  await openSettings(page)

  await page.getByLabel('Asunto').fill('Sumate al equipo de {{municipality}}')
  const body = page.getByRole('textbox', { name: 'Texto' })
  await body.locator('p').first().click()
  await page.keyboard.press('End')
  await page.keyboard.type(' Te esperamos.')
  await page.getByRole('button', { name: 'Guardar texto' }).click()
  await expect(page.getByText('Texto propio del municipio')).toBeVisible()

  await page.getByRole('tab', { name: 'Usuarios' }).click()
  await page.getByRole('button', { name: 'Agregar usuario' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Nombre y apellido').fill('Teresa Texto')
  await form.getByLabel('Email').fill(email)
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()

  const invitation = await theEmailTo(request, email, since)
  expect(invitation.subject).toBe('Sumate al equipo de Noetinger')
  expect(invitation.text).toContain('Hola, Teresa Texto: Te esperamos.')
  expect(invitation.html).toContain('<a href="http://localhost:5174/set-password#')

  // Other tests expect the default text.
  await page.getByRole('tab', { name: 'Configuración' }).click()
  await page.getByRole('button', { name: 'Volver al texto por defecto' }).click()
  // Asked in a modal window, not the browser's popup.
  const question = page.getByRole('dialog', { name: 'Volver al texto por defecto' })
  await question.getByRole('button', { name: 'Volver al texto por defecto' }).click()
  await expect(question).toBeHidden()
  await expect(page.getByText('Texto por defecto', { exact: true })).toBeVisible()
})

test('notifications go to the list of recipients the administrator saved', async ({
  page,
  request,
}) => {
  test.slow()
  const since = new Date()
  const recipient = `avisos-${Date.now()}@example.test`
  await openSettings(page)

  const field = page.getByLabel('Destinatarios de los avisos')
  await field.fill(`${recipient},  intendencia@noetinger.test`)
  await page.getByRole('button', { name: 'Guardar destinatarios' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()
  await page.reload()
  await expect(field).toHaveValue(`${recipient}, intendencia@noetinger.test`)

  backendCommand('notify')

  await expect
    .poll(async () => (await emailsTo(request, recipient, since)).map((email) => email.subject))
    .toContain('Hitos vencidos en Noetinger')
  // With a list, the dashboard administrators no longer get them.
  const toAdmin = await emailsTo(request, 'admin@noetinger.test', since)
  expect(toAdmin.map((email) => email.subject)).not.toContain('Hitos vencidos en Noetinger')
  await configureNoetinger(page, { notification_emails: [] })
})

test('single sign-on is offered only once the administrator allows it', async ({ page }) => {
  await configureNoetinger(page, { sso_enabled: false })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Ingresar a gobernar360' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Ingresar con inicio de sesión único' })).toHaveCount(
    0,
  )

  await openSettings(page)
  await page.getByRole('tab', { name: 'Acceso' }).click()
  const toggle = page.getByRole('switch', { name: /Permitir ingresar con inicio de sesión único/ })
  await toggle.click()
  await expect(toggle).toBeChecked()
  await logout(page)

  await page.getByRole('link', { name: 'Ingresar con inicio de sesión único' }).click()
  await page.getByLabel('Email').fill('lectura@noetinger.test')
  await page.getByLabel('Contraseña').fill('gobernar360-demo')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()
  await expect(page.getByRole('banner').getByText('Leo Lectura')).toBeVisible()
})

test('the configuration is in tabs that keep what is being typed', async ({ page }) => {
  // No background is needed: the tests run offline.
  await page.route(/tile\.openstreetmap\.org/, (route) => route.abort())
  await openSettings(page)
  const tab = (name: string) => page.getByRole('tab', { name })
  const body = page.getByRole('textbox', { name: 'Texto' })
  await body.locator('p').first().click()
  await page.keyboard.type('Sin guardar. ')

  await tab('Acceso').click()
  await expect(page).toHaveURL(/\/admin\/settings\/access$/)
  await expect(page.getByRole('switch')).toBeVisible()
  await expect(body).toBeHidden()
  await tab('Mapas y zonas').click()
  await expect(page).toHaveURL(/\/admin\/settings\/maps$/)
  // The map, drawn only now, opens on the zones.
  await expect(page.getByRole('region', { name: 'Vista previa del mapa' }).getByText('Centro')).toBeInViewport()

  await page.goBack()
  await expect(page.getByRole('switch')).toBeVisible()
  await tab('Correos').click()
  await expect(page).toHaveURL(/\/admin\/settings$/)
  await expect(body).toContainText('Sin guardar.')
  await expect(page.getByRole('button', { name: 'Guardar texto' })).toBeEnabled()

  await tab('Mapas y zonas').click()
  await expect(page.getByRole('region', { name: 'Vista previa del mapa' }).getByText('Centro')).toBeInViewport()
  await page.reload()
  await expect(tab('Mapas y zonas')).toHaveAttribute('aria-selected', 'true')
})
