import { expect, type Page, test } from '@playwright/test'

import { login, sidebar, statValue } from './helpers.ts'

const NEW_PROCEDURE = 'Permiso de poda'

async function openDashboard(page: Page) {
  await sidebar(page).getByRole('link', { name: 'Trámites' }).click()
  await expect(page.getByRole('heading', { name: 'Trámites', level: 2 })).toBeVisible()
}

/** Yearly volume the opportunities report attributes to a source. */
async function volumeOf(page: Page, source: string): Promise<number> {
  const row = page.getByRole('row', { name: new RegExp(`^${source}`) })
  await expect(row).toBeVisible()
  return Number((await row.getByRole('cell').last().innerText()).replace(/\D/g, ''))
}

test('editor adds a procedure with a requirement and the opportunities grow', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  const proceduresBefore = await statValue(page, 'Trámites vigentes')
  await page.getByRole('tab', { name: 'Oportunidades' }).click()
  const volumeBefore = await volumeOf(page, 'Rentas municipal')

  await page.getByRole('tab', { name: 'Trámites' }).click()
  await page.getByRole('button', { name: 'Agregar trámite' }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Nombre').fill(NEW_PROCEDURE)
  await form.getByLabel('Área responsable').selectOption({ label: 'Obras Privadas' })
  await form.getByLabel('Cantidad estimada por año').fill('75')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await page.getByRole('link', { name: NEW_PROCEDURE }).click()

  await expect(page.getByText('Este trámite todavía no tiene requisitos cargados.')).toBeVisible()
  await page.getByRole('button', { name: 'Agregar requisito' }).click()
  const link = page.getByRole('dialog')
  await link.getByLabel('Requisito').selectOption({ label: 'Libre deuda municipal' })
  await link.getByRole('button', { name: 'Guardar' }).click()
  const row = page.getByRole('row', { name: /Libre deuda municipal/ })
  await expect(row).toContainText('Rentas municipal')

  await page.getByRole('tab', { name: 'Oportunidades' }).click()
  await expect.poll(() => volumeOf(page, 'Rentas municipal')).toBe(volumeBefore + 75)
  await page.getByRole('tab', { name: 'Resumen' }).click()
  await expect.poll(() => statValue(page, 'Trámites vigentes')).toBe(proceduresBefore + 1)
})

test('a procedure taken out of service leaves the counts', async ({ page }) => {
  await login(page, 'carga@noetinger.test')
  await openDashboard(page)
  const proceduresBefore = await statValue(page, 'Trámites vigentes')

  await page.getByRole('tab', { name: 'Trámites' }).click()
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('poda')
  await page.getByRole('link', { name: NEW_PROCEDURE }).click()
  await page.getByRole('button', { name: 'Editar', exact: true }).click()
  await page.getByRole('dialog').getByRole('checkbox', { name: 'Vigente' }).uncheck()
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Dado de baja')).toBeVisible()

  await page.getByRole('tab', { name: 'Resumen' }).click()
  await expect.poll(() => statValue(page, 'Trámites vigentes')).toBe(proceduresBefore - 1)
})

test('viewer reads the inventory but cannot change it', async ({ page }) => {
  await login(page, 'lectura@noetinger.test')
  await openDashboard(page)

  await expect(page.getByRole('tab', { name: 'Parámetros' })).toHaveCount(0)
  await page.getByRole('tab', { name: 'Trámites' }).click()
  await expect(page.getByRole('link', { name: 'Habilitación comercial', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Agregar trámite' })).toHaveCount(0)
  await page.getByRole('tab', { name: 'Requisitos' }).click()
  await expect(page.getByRole('row', { name: /^DNI/ })).toContainText('RENAPER')
  await expect(page.getByRole('button', { name: 'Agregar requisito' })).toHaveCount(0)
  const refused = await page.request.post('/api/dashboards/procedures/requirements', {
    data: { name: 'x' },
    headers: { 'X-Requested-With': 'gobernar360' },
  })
  expect(refused.status()).toBe(403)
})

test('admin adds a source and uses it in a requirement', async ({ page }) => {
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)

  await page.getByRole('tab', { name: 'Parámetros' }).click()
  await page.getByRole('button', { name: 'Agregar fuente' }).click()
  const source = page.getByRole('dialog')
  await source.getByLabel('Nombre').fill('Registro de la Propiedad Automotor')
  await source.getByLabel('Nivel').selectOption({ label: 'Nacional' })
  await expect(source.getByLabel('Área')).toHaveCount(0)
  await source.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('row', { name: /Registro de la Propiedad Automotor/ })).toContainText(
    'Nacional',
  )

  await page.getByRole('tab', { name: 'Requisitos' }).click()
  await page.getByRole('button', { name: 'Agregar requisito' }).click()
  const requirement = page.getByRole('dialog')
  await requirement.getByLabel('Requisito').fill('Título del automotor')
  await requirement
    .getByLabel('Fuente')
    .selectOption({ label: 'Registro de la Propiedad Automotor (Nacional)' })
  await requirement.getByRole('button', { name: 'Guardar' }).click()
  // The list shows ten at a time: find the new one by searching.
  await page.getByRole('searchbox', { name: 'Buscar' }).fill('automotor')
  await expect(page.getByRole('row', { name: /Título del automotor/ })).toContainText(
    'Registro de la Propiedad Automotor',
  )
})

test('the other municipality has the dashboard and none of this data', async ({ page }) => {
  await login(page, 'admin@comuna-demo.test')
  await openDashboard(page)

  await expect(page.getByText('Todavía no hay trámites cargados')).toBeVisible()
  await page.getByRole('tab', { name: 'Requisitos' }).click()
  await expect(page.getByText('Todavía no hay requisitos cargados.')).toBeVisible()
})

test('a level on a procedure and a requirement on paper change the summary', async ({ page }) => {
  const figures = async () => {
    await page.getByRole('tab', { name: 'Resumen' }).click()
    const section = page.getByRole('region', { name: 'Digitalización' })
    const number = async (label: string) => {
      const card = section.locator('[data-indicator]').filter({ hasText: label }).first()
      return Number((await card.locator('p').nth(1).innerText()).replace(/\D/g, ''))
    }
    await expect(section).toBeVisible()
    return { cidi: await number('Con ingreso por CiDi'), digital: await number('100 % digitales') }
  }
  const open = async (name: string) => {
    await page.getByRole('tab', { name: 'Trámites' }).click()
    await page.getByRole('searchbox', { name: 'Buscar' }).fill(name)
    await page.getByRole('link', { name, exact: true }).click()
    await expect(page.getByRole('heading', { name })).toBeVisible()
  }
  const numbering = 'Certificado de numeración domiciliaria'
  await login(page, 'admin@noetinger.test')
  await openDashboard(page)
  const before = await figures()

  // In person only: the form refuses.
  await open('Permiso de obra')
  await page.getByRole('button', { name: 'Editar', exact: true }).click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Ingreso con CiDi').selectOption('2')
  await expect(form.getByText('no tiene ingreso con CiDi', { exact: false })).toBeVisible()
  await expect(form.getByRole('button', { name: 'Guardar' })).toBeDisabled()
  await form.getByRole('button', { name: 'Cancelar' }).click()

  await open(numbering)
  await expect(page.getByText('100 % digital', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Editar', exact: true }).click()
  await form.getByLabel('Ingreso con CiDi').selectOption('2')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Nivel 2 – Verificado', { exact: true })).toBeVisible()
  // The summary shows the old figures while it refetches: wait for the new ones.
  await expect.poll(figures).toEqual({ cidi: before.cidi + 1, digital: before.digital })
  await expect(
    page.getByRole('table', { name: 'Trámites por nivel de CiDi' }).getByRole('row', { name: /^Nivel 2/ }),
  ).toBeVisible()

  // What has to be brought on paper cannot be done from home, unless it is optional.
  await open(numbering)
  await page.getByRole('button', { name: 'Agregar requisito' }).click()
  await form.getByLabel('Requisito').selectOption({ label: 'Foto carnet' })
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('row', { name: /Foto carnet/ })).toBeVisible()
  await expect(page.getByText('100 % digital', { exact: true })).toHaveCount(0)
  await expect.poll(figures).toEqual({ cidi: before.cidi + 1, digital: before.digital - 1 })
  await open(numbering)
  await page.getByRole('button', { name: 'Cambiar requisito: Foto carnet' }).click()
  await form.getByRole('checkbox').uncheck()
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('100 % digital', { exact: true })).toBeVisible()
  await expect.poll(async () => (await figures()).digital).toBe(before.digital)

  const csv = await page.request.get('/api/dashboards/procedures/export/procedures.csv')
  const [header, ...rows] = (await csv.text()).trim().split(/\r?\n/)
  expect(header.endsWith('cidi_level')).toBe(true)
  expect(rows.find((row) => row.startsWith(numbering))).toMatch(/,2$/)
})
