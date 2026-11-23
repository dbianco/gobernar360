// Local OpenID Connect provider for trying single sign-on without real credentials.
// Development only: the accounts, client secret and cookie keys below are public.
//
// Built on oidc-provider (an OpenID Certified implementation). It signs in the accounts
// of accounts.json with their password, requires PKCE, and skips the consent screen
// because gobernar360 is its only client. It asks for the account every time, so
// signing out of gobernar360 and in again can try a different one.

import { generateKeyPairSync } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { createServer } from 'node:http'

import Provider, { interactionPolicy } from 'oidc-provider'

const PORT = Number(process.env.PORT ?? 5556)
const ISSUER = process.env.ISSUER ?? `http://localhost:${PORT}`
const CLIENT_ID = process.env.CLIENT_ID ?? 'gobernar360'
const CLIENT_SECRET = process.env.CLIENT_SECRET ?? 'gobernar360-dev-secret'
// The web app's origins: the dev server and the one the browser tests start.
const APP_URLS = (process.env.APP_URLS ?? 'http://localhost:5173,http://localhost:5174').split(',')

const accounts = JSON.parse(readFileSync(new URL('./accounts.json', import.meta.url), 'utf8'))
const byEmail = new Map(accounts.map((account) => [account.email.toLowerCase(), account]))
const byId = new Map(accounts.map((account) => [account.sub, account]))

// A new signing key on every start; relying parties fetch it from the JWKS endpoint.
const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 })
const signingKey = { ...privateKey.export({ format: 'jwk' }), kid: `dev-${Date.now()}`, use: 'sig', alg: 'RS256' }

// Every sign-in shows the login form, except when coming back from it.
const policy = interactionPolicy.base()
policy.get('login').checks.push(
  new interactionPolicy.Check('always', 'The development provider always asks', (ctx) =>
    ctx.oidc.result?.login
      ? interactionPolicy.Check.NO_NEED_TO_PROMPT
      : interactionPolicy.Check.REQUEST_PROMPT,
  ),
)

const provider = new Provider(ISSUER, {
  clients: [
    {
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      redirect_uris: APP_URLS.map((url) => `${url}/api/auth/sso/callback`),
      grant_types: ['authorization_code'],
      response_types: ['code'],
      token_endpoint_auth_method: 'client_secret_basic',
    },
  ],
  jwks: { keys: [signingKey] },
  cookies: { keys: ['gobernar360-dev-oidc-cookie-key'] },
  claims: {
    openid: ['sub'],
    email: ['email', 'email_verified'],
    profile: ['name'],
  },
  // Every client must use PKCE with S256.
  pkce: { required: () => true },
  features: { devInteractions: { enabled: false } },
  interactions: { policy, url: (_ctx, interaction) => `/interaction/${interaction.uid}` },
  async findAccount(_ctx, sub) {
    const account = byId.get(sub)
    if (!account) return undefined
    return {
      accountId: sub,
      async claims() {
        return {
          sub,
          email: account.email,
          email_verified: account.email_verified,
          name: account.name,
        }
      },
    }
  },
  // First-party client: grant what it asks for instead of showing a consent screen.
  async loadExistingGrant(ctx) {
    const existing =
      ctx.oidc.result?.consent?.grantId || ctx.oidc.session.grantIdFor(ctx.oidc.client.clientId)
    if (existing) return ctx.oidc.provider.Grant.find(existing)
    const grant = new ctx.oidc.provider.Grant({
      clientId: ctx.oidc.client.clientId,
      accountId: ctx.oidc.session.accountId,
    })
    grant.addOIDCScope('openid email profile')
    grant.addOIDCClaims(['email', 'email_verified', 'name'])
    await grant.save()
    return grant
  },
})

const escape = (value) =>
  String(value).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

function loginPage(uid, { email = '', error = '' } = {}) {
  const rows = accounts
    .map(
      (account) =>
        `<tr><td>${escape(account.email)}</td><td>${escape(account.note ?? '')}</td></tr>`,
    )
    .join('')
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Proveedor de identidad de prueba</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem; }
  label { display: block; margin-top: 1rem; }
  input { width: 100%; padding: .5rem; font-size: 1rem; box-sizing: border-box; }
  button { margin-top: 1.25rem; padding: .6rem 1.2rem; font-size: 1rem; }
  .error { color: #b00020; }
  table { margin-top: 2rem; border-collapse: collapse; font-size: .875rem; }
  td { padding: .2rem .6rem .2rem 0; vertical-align: top; }
</style>
</head>
<body>
<h1>Proveedor de identidad de prueba</h1>
<p>Solo para desarrollo. Todas las cuentas usan la contraseña <code>gobernar360-demo</code>.</p>
${error ? `<p class="error" role="alert">${escape(error)}</p>` : ''}
<form method="post" action="/interaction/${escape(uid)}/login">
  <label>Email <input name="email" type="email" autocomplete="username" value="${escape(email)}" required autofocus></label>
  <label>Contraseña <input name="password" type="password" autocomplete="current-password" required></label>
  <button type="submit">Ingresar</button>
</form>
<table><caption>Cuentas de prueba</caption>${rows}</table>
</body>
</html>`
}

async function readForm(req) {
  let body = ''
  for await (const chunk of req) body += chunk
  return Object.fromEntries(new URLSearchParams(body))
}

function send(res, status, html) {
  res.writeHead(status, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
  res.end(html)
}

async function interaction(req, res) {
  const details = await provider.interactionDetails(req, res)
  const uid = details.uid
  if (details.prompt.name !== 'login') {
    // Consent is never asked (see loadExistingGrant); finish whatever else comes up.
    return provider.interactionFinished(req, res, {}, { mergeWithLastSubmission: true })
  }
  if (req.method === 'GET') return send(res, 200, loginPage(uid))

  const form = await readForm(req)
  const account = byEmail.get(String(form.email ?? '').trim().toLowerCase())
  if (!account || form.password !== account.password) {
    return send(res, 200, loginPage(uid, { email: form.email, error: 'Email o contraseña incorrectos.' }))
  }
  return provider.interactionFinished(
    req,
    res,
    { login: { accountId: account.sub } },
    { mergeWithLastSubmission: false },
  )
}

const oidc = provider.callback()

createServer((req, res) => {
  if (req.url.startsWith('/interaction/')) {
    interaction(req, res).catch((error) => {
      console.error(error)
      send(res, 400, `<p>No se pudo continuar: ${escape(error.message)}</p>`)
    })
    return
  }
  oidc(req, res)
}).listen(PORT, () => {
  console.log(`OpenID provider for development at ${ISSUER}`)
  console.log(`Discovery: ${ISSUER}/.well-known/openid-configuration`)
})
