import { expect, test } from '@playwright/test'

import { login, sidebar } from './helpers.ts'

const REASON = 'Cambio de gestión: se revisa el convenio.'

test('a suspended municipality stops its signed-in admin at the next click, and resuming brings them back', async ({
  browser,
}) => {
  // The commune's administrator is already working in one browser.
  const adminContext = await browser.newContext()
  const admin = await adminContext.newPage()
  await login(admin, 'admin@comuna-demo.test')
  await sidebar(admin).getByRole('link', { name: 'Proyectos' }).click()
  await expect(admin.getByRole('heading', { name: 'Proyectos', level: 2 })).toBeVisible()

  // The operator suspends it from another one.
  const operatorContext = await browser.newContext()
  const operator = await operatorContext.newPage()
  await login(operator, 'operador@gobernar360.test')
  await operator.getByRole('link', { name: 'Configurar Comuna Demo' }).click()
  await operator.getByRole('button', { name: 'Suspender municipio' }).click()
  const dialog = operator.getByRole('dialog')
  await dialog.getByRole('textbox', { name: 'Motivo' }).fill(REASON)
  await dialog.getByRole('button', { name: 'Suspender municipio' }).click()
  await expect(operator.getByText(`Motivo: ${REASON}`)).toBeVisible()
  await expect(operator.getByText('Desde el', { exact: false })).toContainText(
    'Operador de la plataforma',
  )
  await operator.getByRole('link', { name: '← Municipios' }).click()
  await expect(operator.getByRole('row', { name: /Comuna Demo/ })).toContainText('Suspendido')

  // The admin's next click says so, and nothing of the commune stays on screen.
  await sidebar(admin).getByRole('link', { name: 'Resumen general' }).click()
  await expect(admin.getByRole('heading', { name: 'Comuna Demo está suspendido' })).toBeVisible()
  await expect(sidebar(admin).getByRole('link', { name: 'Proyectos' })).toHaveCount(0)
  const refused = await admin.request.get('/api/overview')
  expect(refused.status()).toBe(403)
  expect((await refused.json()).error.code).toBe('municipality_suspended')

  // Resuming restores everything as it was, in the same session.
  await operator.getByRole('link', { name: 'Configurar Comuna Demo' }).click()
  await operator.getByRole('button', { name: 'Reanudar municipio' }).click()
  await expect(operator.getByText('Activo: sus usuarios pueden trabajar.')).toBeVisible()

  await admin.getByRole('button', { name: 'Volver a intentar' }).click()
  await sidebar(admin).getByRole('link', { name: 'Proyectos' }).click()
  await expect(admin.getByRole('heading', { name: 'Proyectos', level: 2 })).toBeVisible()
  expect((await admin.request.get('/api/overview')).status()).toBe(200)

  await adminContext.close()
  await operatorContext.close()
})
