import { isRecord, requestJson } from './http'

export interface Readiness {
  status: 'ok'
  database: 'ok'
}

export async function fetchReadiness(signal?: AbortSignal): Promise<Readiness> {
  const data = await requestJson('/health/ready', { signal })
  if (
    !isRecord(data) || data.status !== 'ok' || data.database !== 'ok'
  ) {
    throw new Error('Invalid readiness response.')
  }
  return { status: data.status, database: data.database }
}
