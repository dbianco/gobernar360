import { describe, expect, it } from 'vitest'

import { mockApi, mockApiError } from '../test/server'
import { api, ApiError, downloadUrl } from './client'

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
})
