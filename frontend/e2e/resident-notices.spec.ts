import { expect, type Page, test } from '@playwright/test'

import { backendCommand, login, sidebar, theEmailTo } from './helpers.ts'

const NOTE = 'NOTA INTERNA: llamar a la cuadrilla de Pedro'
const MESSAGE = 'Cambiamos la lámpara esta mañana.'

async function open(page: Page, dashboard: string, tab?: string) {
  await sidebar(page).getByRole('link', { name: dashboard, exact: true }).click()
  await expect(page.getByRole('heading', { name: dashboard, level: 2 })).toBeVisible()
  if (tab) await page.getByRole('tab', { name: tab, exact: true }).click()
}

/** Register a complaint and open it. */
async function complain(page: Page, address: string, fill: (dialog: ReturnType<Page['getByRole']>) => Promise<void>) {
  await open(page, 'Reclamos', 'Reclamos')
  await page.getByRole('button', { name: 'Nuevo reclamo' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Dirección').fill(address)
  await fill(form)
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText(address).first()).toBeVisible()
}

async function resolve(page: Page, message?: string) {
  await page.getByRole('button', { name: 'Asignar al área', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Asignar al área', exact: true }).click()
  await page.getByRole('button', { name: 'Marcar como resuelto' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nota', { exact: true }).fill(NOTE)
  if (message) await dialog.getByLabel('Mensaje para el vecino (opcional)').fill(message)
  await dialog.getByRole('button', { name: 'Marcar como resuelto' }).click()
  await expect(dialog).toHaveCount(0)
}

const notices = (page: Page) => page.getByRole('region', { name: 'Avisos al vecino' })

/** Someone the registry does not have, looked up by document. */
async function newResident(
  form: ReturnType<Page['getByRole']>,
  document: string,
  first: string,
  extra: Record<string, string> = {},
) {
  await form.getByText('Vecino con DNI').click()
  await form.getByRole('textbox', { name: 'DNI o CUIL del vecino' }).fill(document)
  await form.getByRole('button', { name: 'Buscar en el padrón' }).click()
  await form.getByRole('textbox', { name: 'Nombre', exact: true }).fill(first)
  await form.getByRole('textbox', { name: 'Apellido' }).fill('Vecina')
  for (const [label, value] of Object.entries(extra)) {
    await form.getByRole('textbox', { name: label, exact: true }).fill(value)
  }
}

test('a resident with a CUIL is told through CiDi, without the internal note', async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')
  await complain(page, 'Belgrano 1', async (form) => {
    await newResident(form, '12345678', 'Clara', { CUIL: '20-12345678-7' })
    await expect(form.getByText('El CUIL no es válido', { exact: false })).toBeVisible()
    await form.getByRole('textbox', { name: 'CUIL', exact: true }).fill('20-12345678-6')
    await expect(form.getByText('El CUIL no es válido', { exact: false })).toHaveCount(0)
  })
  await expect(notices(page).getByText('Todavía no se le avisó nada.')).toBeVisible()
  await resolve(page, MESSAGE)
  await expect(notices(page).getByText('En cola')).toBeVisible()

  backendCommand('send-notices')
  await page.reload()

  await expect(notices(page).getByText('Entregado a CiDi', { exact: true })).toBeVisible()
  await expect(
    notices(page).getByText('no afirma efectos legales', { exact: false }),
  ).toBeVisible()
  const inbox = backendCommand('cidi-fake-inbox')
  expect(inbox).toContain('To 20123456786: Tu reclamo')
  expect(inbox).toContain(MESSAGE)
  expect(inbox).not.toContain('NOTA INTERNA')
})

test('a resident with only an address is emailed, and one with nothing is shown as such', async ({
  page,
  request,
}) => {
  const since = new Date()
  const address = `vecina-${since.getTime()}@example.test`
  await login(page, 'admin@comuna-demo.test')
  await complain(page, 'Belgrano 2', (form) =>
    newResident(form, '28765432', 'Elsa', { Email: address }),
  )
  await resolve(page, MESSAGE)
  await expect(notices(page).getByText('Enviado por correo')).toBeVisible()
  const email = await theEmailTo(request, address, since)
  expect(email.text).toContain(MESSAGE)
  expect(email.text + email.html).not.toContain('NOTA INTERNA')

  await complain(page, 'Belgrano 3', (form) => newResident(form, '27654321', 'Rita'))
  await resolve(page)
  await expect(notices(page).getByText('Sin medio para avisar')).toBeVisible()
})

test('the municipality sets how residents are told, and its secrets do not come back', async ({
  page,
}) => {
  const secret = 'una-clave-inventada-9f3'
  await login(page, 'admin@comuna-demo.test')
  await sidebar(page).getByRole('link', { name: 'Configuración' }).click()
  await expect(page.getByRole('heading', { name: 'Avisos a vecinos' })).toBeVisible()
  const channel = page.getByRole('combobox', { name: 'Medio para avisar a los vecinos' })
  await expect(channel).toHaveValue('cidi_then_email')
  await page.getByLabel('Ordenanza que respalda el uso de CiDi').fill('Ordenanza 99/2026')
  await page.getByLabel('Nombre de la clave nueva').fill('api_key')
  await page.getByLabel('Valor de la clave nueva').fill(secret)
  await page.getByRole('button', { name: 'Guardar avisos a vecinos' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Ordenanza que respalda el uso de CiDi')).toHaveValue(
    'Ordenanza 99/2026',
  )
  await expect(page.getByText(/^Cargado el /)).toBeVisible()
  const answer = await page.request.get('/api/admin/settings/notices')
  expect(await answer.text()).toContain('api_key')
  expect((await answer.text()) + (await page.content())).not.toContain(secret)

  const form = await page.request.get('/api/admin/settings/notices/adhesion-request')
  expect(await form.text()).toContain('gobernar360 – Comuna Demo')
})

test('a municipality that has not adhered cannot choose CiDi, nor see what the other has', async ({
  page,
}) => {
  await login(page, 'admin@noetinger.test')
  await sidebar(page).getByRole('link', { name: 'Configuración' }).click()
  const channel = page.getByRole('combobox', { name: 'Medio para avisar a los vecinos' })
  await expect(channel).toHaveValue('email')
  await expect(channel.getByRole('option', { name: 'Solo CiDi' })).toBeDisabled()
  await expect(page.getByText('Para poder elegir CiDi falta:', { exact: false })).toBeVisible()
  await expect(page.getByText('Ninguna clave cargada.')).toBeVisible()
  const refused = await page.request.put('/api/admin/settings/notices', {
    data: { resident_notice_channel: 'cidi' },
    headers: { 'X-Requested-With': 'gobernar360' },
  })
  expect(refused.status()).toBe(422)

  const found = await page.request.get('/api/dashboards/social/people/lookup?cuil=20123456786')
  expect(await found.json()).toMatchObject({ person: null })
})
