import { execFileSync } from 'node:child_process'
import path from 'node:path'

import { type APIRequestContext, expect, type Locator, type Page } from '@playwright/test'

import { backendEnv } from '../playwright.config.ts'

export const PASSWORD = 'gobernar360-demo'

export async function login(page: Page, email: string, password = PASSWORD) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Contraseña').fill(password)
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

/** Choose somebody in a list of people, typing part of their name. */
export async function choosePerson(page: Page, list: Locator, typed: string, name: string) {
  await list.fill(typed)
  await page.getByRole('option', { name }).click()
}

const MAILPIT = process.env.MAILPIT_URL ?? 'http://localhost:8025'

/** Run the email worker once, as `uv run gobernar360 send-email` would by hand. */
export function deliverEmails() {
  backendCommand('send-email')
}

interface MailpitSummary {
  ID: string
  To: { Address: string }[]
  Subject: string
  Created: string
}

export interface Email {
  subject: string
  text: string
  html: string
}

/** Emails the mail catcher received for an address since `since`, oldest first. */
export async function emailsTo(
  request: APIRequestContext,
  address: string,
  since: Date,
): Promise<Email[]> {
  const list = await (await request.get(`${MAILPIT}/api/v1/messages?limit=500`)).json()
  const matching = (list.messages as MailpitSummary[])
    .filter(
      (message) =>
        message.To.some((to) => to.Address.toLowerCase() === address.toLowerCase()) &&
        Date.parse(message.Created) >= since.getTime() - 1000,
    )
    .reverse()
  return Promise.all(
    matching.map(async (summary) => {
      const message = await (await request.get(`${MAILPIT}/api/v1/message/${summary.ID}`)).json()
      return {
        subject: message.Subject as string,
        text: message.Text as string,
        html: message.HTML as string,
      }
    }),
  )
}

/** Deliver pending emails and return the only one sent to `address` since `since`. */
export async function theEmailTo(
  request: APIRequestContext,
  address: string,
  since: Date,
): Promise<Email> {
  deliverEmails()
  let emails: Email[] = []
  await expect
    .poll(async () => (emails = await emailsTo(request, address, since)).length, {
      message: `one email to ${address}`,
    })
    .toBe(1)
  return emails[0]
}

/** The set-password link in an email. */
export function passwordLink(email: Email): string {
  const match = email.text.match(/https?:\/\/\S+\/set-password#[\w-]+/)
  expect(match, email.text).not.toBeNull()
  return match![0]
}

/** Run a gobernar360 command against the browser-test database; what it says. */
export function backendCommand(...args: string[]): string {
  return execFileSync('uv', ['run', 'gobernar360', ...args], {
    cwd: path.resolve(import.meta.dirname, '../../backend'),
    env: { ...process.env, ...backendEnv },
    stdio: 'pipe',
    encoding: 'utf-8',
  })
}

/** Change Noetinger's configuration as its administrator, keeping what is not given. */
export async function configureNoetinger(
  page: Page,
  changes: { sso_enabled?: boolean; notification_emails?: string[] },
) {
  // Whoever the page was signed in as, this runs as the administrator.
  await page.context().clearCookies()
  await login(page, 'admin@noetinger.test')
  const current = await (await page.request.get('/api/admin/settings')).json()
  const response = await page.request.put('/api/admin/settings', {
    headers: { 'X-Requested-With': 'gobernar360' },
    data: {
      notification_emails: current.notification_emails,
      sso_enabled: current.sso_enabled,
      ...changes,
    },
  })
  expect(response.status()).toBe(200)
  await logout(page)
}
