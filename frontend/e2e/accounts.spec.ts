import { expect, test } from '@playwright/test'

import {
  configureNoetinger,
  emailsTo,
  login,
  logout,
  passwordLink,
  sidebar,
  theEmailTo,
} from './helpers.ts'

// Email goes through the real outbox, `gobernar360 send-email` and the mail catcher.

test('an administrator invites someone, who chooses a password from the email and signs in', async ({
  page,
  request,
}) => {
  // Two sign-ins and a run of the email worker.
  test.slow()
  const since = new Date()
  const email = `invitada-${Date.now()}@noetinger.test`
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Usuarios' }).click()

  await page.getByRole('button', { name: 'Agregar usuario' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Nombre y apellido').fill('Irene Invitada')
  await form.getByLabel('Email').fill(email)
  // Nobody types a password for someone else.
  await expect(form.locator('input[type="password"]')).toHaveCount(0)
  await form.getByRole('combobox', { name: 'Acceso a Proyectos' }).selectOption('Lectura')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByText(`Le enviamos un email a ${email}`)).toBeVisible()
  await logout(page)

  const invitation = await theEmailTo(request, email, since)
  expect(invitation.subject).toBe('Te dieron acceso a Noetinger en gobernar360')
  expect(invitation.text).toContain('Ana Administradora te dio acceso a Noetinger')
  const link = passwordLink(invitation)

  await page.goto(link)
  await expect(
    page.getByRole('heading', { name: 'Te damos la bienvenida a gobernar360' }),
  ).toBeVisible()
  await page.getByLabel('Contraseña nueva').fill('clave-de-irene-123')
  await page.getByLabel('Repetí la contraseña').fill('clave-de-irene-123')
  await page.getByRole('button', { name: 'Guardar contraseña' }).click()
  await expect(page.getByText('Tu contraseña quedó guardada. Ya podés ingresar.')).toBeVisible()
  await expect(page.getByLabel('Email')).toHaveValue(email)

  await page.getByLabel('Contraseña').fill('clave-de-irene-123')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(sidebar(page).getByRole('link', { name: 'Proyectos' })).toBeVisible()
  await logout(page)

  // The link works once.
  await page.goto(link)
  await expect(page.getByRole('heading', { name: 'Este enlace ya no es válido' })).toBeVisible()
})

test('"forgot my password" says the same for any email and only emails real accounts', async ({
  page,
  request,
}) => {
  const since = new Date()
  const unknown = `nadie-${Date.now()}@noetinger.test`
  const known = 'lectura@noetinger.test'
  const messages: string[] = []

  for (const email of [unknown, known]) {
    await page.goto('/login')
    await page.getByRole('link', { name: '¿Olvidaste tu contraseña?' }).click()
    await page.getByLabel('Email').fill(email)
    await page.getByRole('button', { name: 'Enviar enlace' }).click()
    const answer = page.getByRole('alert')
    await expect(answer).toContainText('te enviamos un enlace')
    messages.push((await answer.innerText()).replace(email, '<email>'))
  }

  expect(messages[0]).toBe(messages[1])
  const recovery = await theEmailTo(request, known, since)
  expect(recovery.subject).toBe('Elegí una contraseña nueva para gobernar360')
  expect(await emailsTo(request, unknown, since)).toEqual([])
  // The demo password stays: the link is not used here.
  await login(page, known)
})

test('single sign-on signs in a demo user through the local identity provider', async ({
  page,
}) => {
  await configureNoetinger(page, { sso_enabled: true })
  await page.goto('/login')
  await page.getByRole('link', { name: 'Ingresar con inicio de sesión único' }).click()

  await expect(
    page.getByRole('heading', { name: 'Proveedor de identidad de prueba' }),
  ).toBeVisible()
  await page.getByLabel('Email').fill('carga@noetinger.test')
  await page.getByLabel('Contraseña').fill('gobernar360-demo')
  await page.getByRole('button', { name: 'Ingresar' }).click()

  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()
  await expect(page.getByRole('banner').getByText('Noetinger')).toBeVisible()
  await logout(page)
})

test('single sign-on does not let in an email the provider has not verified', async ({ page }) => {
  await configureNoetinger(page, { sso_enabled: true })
  await page.goto('/login')
  await page.getByRole('link', { name: 'Ingresar con inicio de sesión único' }).click()
  await page.getByLabel('Email').fill('sinacceso@noetinger.test')
  await page.getByLabel('Contraseña').fill('gobernar360-demo')
  await page.getByRole('button', { name: 'Ingresar' }).click()

  await expect(page.getByText('no confirmó que el email sea tuyo')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ingresar a gobernar360' })).toBeVisible()
})
