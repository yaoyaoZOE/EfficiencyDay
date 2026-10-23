export const currentUser = {
  id: 1,
  username: 'demo',
  timezone: 'Asia/Shanghai',
  csrf_token: 'test-csrf-token',
}

export const workItem = {
  id: 1,
  title: '准备项目周报',
  status: 'pending',
  urgency: null,
  importance: null,
  color_key: null,
  due_on: '2026-10-25',
  started_on: null,
  completed_on: null,
  background: '汇总本周进展',
  goal: '明确下周重点',
  result: null,
  reflection: null,
  version: 1,
  created_at: '2026-10-23T04:00:00Z',
  updated_at: '2026-10-23T04:00:00Z',
}

export function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
