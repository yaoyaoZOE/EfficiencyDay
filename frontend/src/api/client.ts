import { isRecord, requestJson } from './http'

export interface CurrentUser {
  id: number
  username: string
  timezone: string
  csrf_token: string
}

export const statuses = ['pending', 'in_progress', 'completed', 'cancelled'] as const
export const colors = ['gray', 'blue', 'green', 'yellow', 'orange', 'red', 'purple'] as const
export type WorkItemStatus = typeof statuses[number]
export type ColorKey = typeof colors[number]

export interface WorkItem {
  id: number
  title: string
  status: WorkItemStatus
  urgency: boolean | null
  importance: boolean | null
  color_key: ColorKey | null
  due_on: string | null
  started_on: string | null
  completed_on: string | null
  background: string | null
  goal: string | null
  result: string | null
  reflection: string | null
  version: number
  created_at: string
  updated_at: string
}

export type WorkItemCreate = Pick<WorkItem, 'title'> & Partial<Pick<WorkItem,
  'urgency' | 'importance' | 'color_key' | 'due_on' | 'background' | 'goal'
>>

export interface WorkItemPage {
  items: WorkItem[]
  limit: number
  offset: number
}

function isInteger(value: unknown, minimum: number): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum
}

function isDate(value: unknown): boolean {
  return value === null || (
    typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(`${value}T00:00:00Z`)) &&
    new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value
  )
}

function isTimestamp(value: unknown): boolean {
  return typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value))
}

function isTimezone(value: unknown): value is string {
  if (typeof value !== 'string' || !value) return false
  try {
    new Intl.DateTimeFormat('zh-CN', { timeZone: value })
    return true
  } catch (error) {
    if (error instanceof RangeError) return false
    throw error
  }
}

function isWorkItem(value: unknown): value is WorkItem {
  return isRecord(value) && isInteger(value.id, 1) &&
    typeof value.title === 'string' && value.title.length > 0 &&
    statuses.some(status => status === value.status) &&
    (value.urgency === null || typeof value.urgency === 'boolean') &&
    (value.importance === null || typeof value.importance === 'boolean') &&
    (value.color_key === null || colors.some(color => color === value.color_key)) &&
    ['due_on', 'started_on', 'completed_on'].every(key => isDate(value[key])) &&
    ['background', 'goal', 'result', 'reflection'].every(
      key => value[key] === null || typeof value[key] === 'string',
    ) &&
    isInteger(value.version, 1) && isTimestamp(value.created_at) && isTimestamp(value.updated_at)
}

export async function fetchCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  const data = await requestJson('/auth/me', { signal })
  if (
    !isRecord(data) || !isInteger(data.id, 1) ||
    typeof data.username !== 'string' || !data.username ||
    !isTimezone(data.timezone) ||
    typeof data.csrf_token !== 'string' || !data.csrf_token
  ) {
    throw new Error('Invalid current-user response.')
  }
  return { id: data.id, username: data.username, timezone: data.timezone, csrf_token: data.csrf_token }
}

function requireAuthStatus(data: unknown): void {
  if (!isRecord(data) || data.status !== 'ok') throw new Error('Invalid authentication response.')
}

export async function login(username: string, password: string): Promise<void> {
  requireAuthStatus(await requestJson('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  }))
}

export async function logout(csrfToken: string): Promise<void> {
  requireAuthStatus(await requestJson('/auth/logout', {
    method: 'POST', headers: { 'X-CSRF-Token': csrfToken },
  }))
}

export async function fetchWorkItems(
  limit: number, offset: number, signal?: AbortSignal,
): Promise<WorkItemPage> {
  const data = await requestJson(`/work-items?limit=${limit}&offset=${offset}`, { signal })
  if (
    !isRecord(data) || !Array.isArray(data.items) || !data.items.every(isWorkItem) ||
    !isInteger(data.limit, 1) || data.limit > 100 || !isInteger(data.offset, 0) ||
    data.limit !== limit || data.offset !== offset || data.items.length > limit
  ) {
    throw new Error('Invalid work-item list response.')
  }
  return { items: data.items, limit: data.limit, offset: data.offset }
}

export async function fetchWorkItem(id: number, signal?: AbortSignal): Promise<WorkItem> {
  const data = await requestJson(`/work-items/${id}`, { signal })
  if (!isWorkItem(data) || data.id !== id) throw new Error('Invalid work-item response.')
  return data
}

export async function createWorkItem(payload: WorkItemCreate, csrfToken: string): Promise<WorkItem> {
  const data = await requestJson('/work-items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify(payload),
  })
  if (!isWorkItem(data)) throw new Error('Invalid work-item response.')
  return data
}
