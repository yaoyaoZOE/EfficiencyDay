import { describe, expect, it, vi } from 'vitest'
import { fetchReadiness } from './health'

describe('fetchReadiness', () => {
  it('reads readiness through the same-origin API proxy', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', database: 'ok' })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchReadiness()).resolves.toEqual({ status: 'ok', database: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/health/ready',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('surfaces backend failures instead of returning healthy defaults', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Database migrations are not up to date.' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))

    await expect(fetchReadiness()).rejects.toThrow(
      'HTTP 503: Database migrations are not up to date.',
    )
  })

  it('rejects invalid success payloads', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'unknown' })),
    ))
    await expect(fetchReadiness()).rejects.toThrow('Invalid readiness response.')
  })

  it('preserves network errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network unavailable')))
    await expect(fetchReadiness()).rejects.toThrow('Network unavailable')
  })

  it('reports non-JSON proxy failures with their HTTP status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('Bad gateway', { status: 502 }),
    ))
    await expect(fetchReadiness()).rejects.toThrow('HTTP 502: Bad gateway')
  })
})
