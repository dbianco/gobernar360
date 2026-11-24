/** Thin wrapper over fetch for the gobernar360 API. */

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: { field: string; message: string }[]

  constructor(status: number, code: string, message: string, details?: ApiError['details']) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export type Query = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Query
}

function withQuery(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined && value !== '') params.set(key, String(value))
  }
  const search = params.toString()
  return `/api${path}${search ? `?${search}` : ''}`
}

/** URL for a plain link or download, e.g. a CSV export. */
export function downloadUrl(path: string, query?: Query): string {
  return withQuery(path, query)
}

let onSessionLost: (() => void) | null = null
let onMunicipalitySuspended: (() => void) | null = null

/** Register what to do when the API says the session is no longer valid. */
export function setSessionLostHandler(handler: (() => void) | null) {
  onSessionLost = handler
}

/** Register what to do when the API says the active municipality was suspended. */
export function setMunicipalitySuspendedHandler(handler: (() => void) | null) {
  onMunicipalitySuspended = handler
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    // The API rejects unsafe requests without this header (CSRF protection).
    'X-Requested-With': 'gobernar360',
  }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(new URL(withQuery(path, options.query), window.location.origin), {
      method: options.method ?? 'GET',
      credentials: 'include',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'network', 'Could not reach the server.')
  }

  if (response.status === 204) return undefined as T
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = payload?.error
    // Sign-in and profile checks answer 401 as part of normal use; anything else lost its session.
    if (response.status === 401 && !path.startsWith('/auth/')) onSessionLost?.()
    // The operator suspended the municipality while the user was working in it.
    if (error?.code === 'municipality_suspended') onMunicipalitySuspended?.()
    throw new ApiError(
      response.status,
      error?.code ?? 'generic',
      error?.message ?? response.statusText,
      error?.details,
    )
  }
  return payload as T
}
