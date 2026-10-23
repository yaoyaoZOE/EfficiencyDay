export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(`HTTP ${status}: ${message}`)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export async function requestJson(path: string, options: RequestInit = {}): Promise<unknown> {
  const timeout = AbortSignal.timeout(10_000)
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: 'same-origin',
    cache: 'no-store',
    signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout,
  })
  if (!response.ok) {
    let message = response.statusText || 'Request failed'
    if (response.headers.get('content-type')?.includes('application/json')) {
      const payload: unknown = await response.json()
      if (isRecord(payload) && typeof payload.detail === 'string') {
        message = payload.detail
      } else if (isRecord(payload) && Array.isArray(payload.detail)) {
        const details = payload.detail
          .filter(isRecord)
          .filter(detail => typeof detail.msg === 'string')
          .map(detail => `${Array.isArray(detail.loc) ? detail.loc.join('.') : 'request'}: ${detail.msg}`)
        if (details.length > 0) message = details.join('; ')
      }
    } else {
      message = (await response.text()) || message
    }
    throw new ApiError(response.status, message)
  }
  return response.json()
}
