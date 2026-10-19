export interface Readiness {
  status: 'ok'
  database: 'ok'
}

export async function fetchReadiness(signal?: AbortSignal): Promise<Readiness> {
  const timeout = AbortSignal.timeout(10_000)
  const response = await fetch('/api/v1/health/ready', {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  })

  if (!response.ok) {
    let message = response.statusText || 'Request failed'
    if (response.headers.get('content-type')?.includes('application/json')) {
      const payload: unknown = await response.json()
      if (
        typeof payload === 'object' && payload !== null &&
        'detail' in payload && typeof payload.detail === 'string'
      ) {
        message = payload.detail
      }
    } else {
      message = (await response.text()) || message
    }
    throw new Error(`HTTP ${response.status}: ${message}`)
  }

  const data: unknown = await response.json()
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('database' in data) || data.database !== 'ok'
  ) {
    throw new Error('Invalid readiness response.')
  }
  return { status: data.status, database: data.database }
}
