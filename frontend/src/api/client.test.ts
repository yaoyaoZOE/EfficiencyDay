import { describe, expect, it, vi } from 'vitest'
import {
  createWorkItem, fetchCurrentUser, fetchWorkItem, fetchWorkItems, login, logout,
} from './client'
import { currentUser, jsonResponse, workItem } from '../test/fixtures'

describe('authentication API', () => {
  it('restores a validated user with same-origin cookies and no caching', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(currentUser))
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchCurrentUser()).resolves.toEqual(currentUser)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/me', expect.objectContaining({
      credentials: 'same-origin', cache: 'no-store', signal: expect.any(AbortSignal),
    }))
  })

  it('sends login credentials only in the POST body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)
    await login('demo', 'test-password')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ username: 'demo', password: 'test-password' }),
      headers: { 'Content-Type': 'application/json' },
    }))
  })

  it('sends the in-memory CSRF token for logout', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)
    await logout(currentUser.csrf_token)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/logout', expect.objectContaining({
      method: 'POST', headers: { 'X-CSRF-Token': currentUser.csrf_token },
    }))
  })

  it.each([
    { ...currentUser, csrf_token: '' },
    { ...currentUser, id: '1' },
    { ...currentUser, timezone: null },
  ])('rejects an invalid current-user response', async (payload) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(payload)))
    await expect(fetchCurrentUser()).rejects.toThrow('Invalid current-user response.')
  })

  it('rejects success-shaped authentication fallbacks', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ status: 'unknown' })))
    await expect(login('demo', 'test-password')).rejects.toThrow('Invalid authentication response.')
  })
})

describe('work-item API', () => {
  it('loads a bounded page and validates its envelope', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      items: [workItem], limit: 50, offset: 50,
    }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchWorkItems(50, 50)).resolves.toEqual({
      items: [workItem], limit: 50, offset: 50,
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/work-items?limit=50&offset=50', expect.anything())
  })

  it('loads a validated detail response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(workItem))
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchWorkItem(1)).resolves.toEqual(workItem)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/work-items/1', expect.anything())
  })

  it('creates with CSRF and preserves date-only values and unset priorities', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(workItem, 201))
    vi.stubGlobal('fetch', fetchMock)
    const payload = { title: workItem.title, urgency: null, importance: false, due_on: '2026-10-25' }
    await expect(createWorkItem(payload, currentUser.csrf_token)).resolves.toEqual(workItem)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/work-items', expect.objectContaining({
      method: 'POST', body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': currentUser.csrf_token },
    }))
  })

  it.each([
    { ...workItem, status: 'unknown' },
    { ...workItem, urgency: 'yes' },
    { ...workItem, version: 0 },
    { ...workItem, due_on: '2026-02-30' },
    { ...workItem, due_on: '2026-10-25T00:00:00Z' },
    { ...workItem, created_at: 'yesterday' },
    { ...workItem, color_key: 'pink' },
  ])('rejects invalid detail contracts', async (payload) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(payload)))
    await expect(fetchWorkItem(1)).rejects.toThrow('Invalid work-item response.')
  })

  it('rejects a malformed list rather than displaying an empty list', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ items: [], limit: 0, offset: 0 })))
    await expect(fetchWorkItems(50, 0)).rejects.toThrow('Invalid work-item list response.')
  })
})

describe('request errors', () => {
  it('preserves HTTP status for session handling', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Not authenticated.' }, 401)))
    await expect(fetchCurrentUser()).rejects.toMatchObject({
      status: 401, message: 'HTTP 401: Not authenticated.',
    })
  })

  it('surfaces structured validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      detail: [{ loc: ['body', 'title'], msg: 'String should have at least 1 character' }],
    }, 422)))
    await expect(createWorkItem({ title: '' }, 'csrf')).rejects.toThrow(
      'HTTP 422: body.title: String should have at least 1 character',
    )
  })

  it('reports non-JSON proxy errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad gateway', { status: 502 })))
    await expect(fetchCurrentUser()).rejects.toThrow('HTTP 502: Bad gateway')
  })

  it('does not retry an ambiguous create failure', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new DOMException('Timed out', 'TimeoutError'))
    vi.stubGlobal('fetch', fetchMock)
    await expect(createWorkItem({ title: 'draft' }, 'csrf')).rejects.toThrow('Timed out')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('forwards cancellation to the request', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(currentUser))
    vi.stubGlobal('fetch', fetchMock)
    await fetchCurrentUser(controller.signal)
    controller.abort()
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
  })
})
