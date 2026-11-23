import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { mockApi, mockApiError, server } from '../test/server'
import { api, ApiError, downloadUrl, setSessionLostHandler } from './client'

afterEach(() => {
  setSessionLostHandler(null)
  vi.restoreAllMocks()
})

describe('api client', () => {
  it('returns the parsed JSON body', async () => {
    mockApi('get', '/health', { status: 'ok' })

    await expect(api('/health')).resolves.toEqual({ status: 'ok' })
  })

  it('throws ApiError with the server error code', async () => {
    mockApiError('post', '/auth/login', 401, 'invalid_credentials')

    const request = api('/auth/login', { method: 'POST', body: {} })

    await expect(request).rejects.toBeInstanceOf(ApiError)
    await expect(request).rejects.toMatchObject({ status: 401, code: 'invalid_credentials' })
  })

  it('sends the CSRF header on every request', async () => {
    const requests = mockApi('post', '/auth/logout', null, 204)

    await api('/auth/logout', { method: 'POST' })

    expect(requests[0].headers.get('x-requested-with')).toBe('gobernar360')
  })

  it('sends the body as JSON and skips empty query values', async () => {
    const requests = mockApi('post', '/things', { ok: true })

    await api('/things', { method: 'POST', body: { name: 'x' }, query: { a: 1, b: null, c: '' } })

    expect(requests[0].body).toEqual({ name: 'x' })
    expect(requests[0].headers.get('content-type')).toContain('application/json')
    expect(requests[0].url.search).toBe('?a=1')
  })

  it('returns undefined for empty responses', async () => {
    mockApi('delete', '/things/1', null, 204)

    await expect(api('/things/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('builds download urls with the given filters', () => {
    expect(downloadUrl('/export/projects.csv', { year: 2024, axis_id: null })).toBe(
      '/api/export/projects.csv?year=2024',
    )
  })

  it('asks with GET, sending the session cookie and no content type, by default', async () => {
    const requests = mockApi('get', '/health', { status: 'ok' })
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    await api('/health', { query: { flag: false, zero: 0 } })

    const [, init] = fetchSpy.mock.calls[0]
    expect(init).toMatchObject({ method: 'GET', credentials: 'include', body: undefined })
    expect(requests[0].headers.get('content-type')).toBeNull()
    expect(requests[0].url.search).toBe('?flag=false&zero=0')
  })

  it('says the server could not be reached when the request fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(api('/health')).rejects.toMatchObject({
      status: 0,
      code: 'network',
      message: 'Could not reach the server.',
    })
  })

  it('passes on the message and the details of a server error', async () => {
    const details = [{ field: 'name', message: 'required' }]
    mockApi('put', '/things/1', { error: { code: 'validation_error', message: 'Bad.', details } }, 422)

    await expect(api('/things/1', { method: 'PUT', body: {} })).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      code: 'validation_error',
      message: 'Bad.',
      details,
    })
  })

  it('reports an error without a JSON body as generic, with the status text', async () => {
    server.use(
      http.get('*/api/broken', () => new HttpResponse('<html>oops</html>', { status: 502, statusText: 'Bad Gateway' })),
    )

    await expect(api('/broken')).rejects.toMatchObject({
      status: 502,
      code: 'generic',
      message: 'Bad Gateway',
      details: undefined,
    })
  })

  it('says the session was lost when any request outside sign-in answers 401', async () => {
    const lost = vi.fn()
    setSessionLostHandler(lost)
    mockApiError('get', '/projects', 401, 'not_authenticated')
    mockApiError('get', '/auth/me', 401, 'not_authenticated')
    mockApiError('get', '/secret', 403, 'forbidden')

    await expect(api('/auth/me')).rejects.toBeInstanceOf(ApiError)
    await expect(api('/secret')).rejects.toBeInstanceOf(ApiError)
    expect(lost).not.toHaveBeenCalled()
    await expect(api('/projects')).rejects.toMatchObject({ status: 401 })
    expect(lost).toHaveBeenCalledTimes(1)
  })

  it('builds download urls without filters', () => {
    expect(downloadUrl('/export/projects.csv')).toBe('/api/export/projects.csv')
  })
})
