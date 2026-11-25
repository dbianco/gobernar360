import { http, HttpResponse, type JsonBodyType } from 'msw'
import { setupServer } from 'msw/node'

export const STANDARD_MAP = {
  background: {
    key: 'standard',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    max_zoom: 19,
    provider: null,
    tile_size: 256,
    zoom_offset: 0,
  },
  api_key: null,
}
const NO_FIGURES = { values: {}, groups: [], suppressed: false }
const NO_BREAKDOWN = {
  boundaries_as_of: null,
  metrics: [],
  grouping: null,
  zones: [],
  outside: NO_FIGURES,
  unlocated: NO_FIGURES,
  total: NO_FIGURES,
  threshold: null,
}

// Answers that many screens need; tests that care about them mock them themselves.
export const server = setupServer(
  // Every dashboard summary shows its status strip.
  http.get('*/api/dashboards/:key/status', () => HttpResponse.json([])),
  // ...with what was agreed about each month; records show what was agreed about them.
  http.get('*/api/subjects/:key/commitments', () => HttpResponse.json([])),
  http.get('*/api/subjects/:key/:kind/:ref/commitments', () => HttpResponse.json([])),
  // The header asks what one owes and follows; pages offer the people of the municipality.
  http.get('*/api/notifications', () => HttpResponse.json({ mine: [], others: [] })),
  http.get('*/api/members', () => HttpResponse.json([])),
  // The sign-in page asks whether to offer single sign-on.
  http.get('*/api/auth/sso', () => HttpResponse.json({ enabled: false })),
  // Several flows end on the home page.
  http.get('*/api/overview', () => HttpResponse.json([])),
  http.get('*/api/dashboards/:key/evolution', () => HttpResponse.json([])),
  http.get('*/api/dashboards/:key/evolution/months', ({ request }) =>
    HttpResponse.json({
      year: Number(new URL(request.url).searchParams.get('year')),
      indicators: [],
      months: [],
    }),
  ),
  http.get('*/api/dashboards/:key/targets', () => HttpResponse.json([])),
  http.get('*/api/overview/combined', () => HttpResponse.json([])),
  // Summaries, detail screens and the home page show the geographic layer: no zones, no
  // locations.
  http.get('*/api/map-background', () => HttpResponse.json(STANDARD_MAP)),
  http.get('*/api/zones', () => HttpResponse.json([])),
  http.get('*/api/dashboards/:key/geo/:record/zones', () => HttpResponse.json(NO_BREAKDOWN)),
  http.get('*/api/dashboards/:key/geo/:record/unzoned', () =>
    HttpResponse.json({ items: [], total: 0 }),
  ),
  http.get('*/api/dashboards/:key/geo/:record/:id/location', () =>
    HttpResponse.json({ location: null, kinds: ['Point'], zones: [] }),
  ),
)

type Method = 'get' | 'post' | 'put' | 'patch' | 'delete'

export interface RecordedRequest {
  url: URL
  body: unknown
  headers: Headers
}

/**
 * Answer `method path` with a JSON body and record the requests received.
 * `path` is relative to /api, e.g. "/auth/me".
 */
export function mockApi(
  method: Method,
  path: string,
  body: JsonBodyType | ((request: RecordedRequest) => JsonBodyType) = null,
  status = 200,
): RecordedRequest[] {
  const requests: RecordedRequest[] = []
  server.use(
    http[method](`*/api${path}`, async ({ request }) => {
      const text = await request.text()
      const recorded = {
        url: new URL(request.url),
        body: text ? JSON.parse(text) : undefined,
        headers: request.headers,
      }
      requests.push(recorded)
      if (status === 204) return new HttpResponse(null, { status })
      return HttpResponse.json(typeof body === 'function' ? body(recorded) : body, { status })
    }),
  )
  return requests
}

export function mockApiError(method: Method, path: string, status: number, code: string) {
  return mockApi(method, path, { error: { code, message: `Server said ${code}` } }, status)
}
