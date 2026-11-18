import { http, HttpResponse, type JsonBodyType } from 'msw'
import { setupServer } from 'msw/node'

export const server = setupServer()

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
