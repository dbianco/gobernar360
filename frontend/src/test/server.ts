import { http, HttpResponse, type JsonBodyType } from 'msw'
import { setupServer } from 'msw/node'

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
