import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import App from './App'
import { currentUser, jsonResponse, workItem } from './test/fixtures'

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const view = render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
  return { ...view, client }
}

function mockApi(options: { authenticated?: boolean; items?: unknown[] } = {}) {
  let authenticated = options.authenticated ?? false
  const items = options.items ?? [workItem]
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/health/ready')) return jsonResponse({ status: 'ok', database: 'ok' })
    if (url.endsWith('/auth/me')) {
      return authenticated ? jsonResponse(currentUser) : jsonResponse({ detail: 'Not authenticated.' }, 401)
    }
    if (url.endsWith('/auth/login')) {
      authenticated = true
      return jsonResponse({ status: 'ok' })
    }
    if (url.endsWith('/auth/logout')) {
      authenticated = false
      return jsonResponse({ status: 'ok' })
    }
    if (url.includes('/work-items?')) {
      const offset = Number(new URL(url, 'http://localhost').searchParams.get('offset'))
      return jsonResponse({ items: offset === 0 ? items : [], limit: 50, offset })
    }
    if (url.endsWith('/work-items') && init?.method === 'POST') {
      const payload: unknown = JSON.parse(String(init.body))
      return jsonResponse({ ...workItem, ...Object(payload), id: 2 }, 201)
    }
    if (url.match(/\/work-items\/\d+$/)) {
      return jsonResponse({ ...workItem, id: Number(url.split('/').at(-1)) })
    }
    throw new Error(`Unexpected API request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function signIn() {
  fireEvent.change(await screen.findByLabelText('用户名'), { target: { value: 'demo' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'test-password' } })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
  await screen.findByRole('button', { name: '退出登录' })
}

function fillTitle(title: string) {
  fireEvent.change(screen.getByLabelText('标题'), { target: { value: title } })
}

it('shows real backend and database readiness', async () => {
  mockApi()
  renderApp()
  fireEvent.click(screen.getByText('开发环境状态'))
  expect(await screen.findByText('后端与数据库已就绪')).toBeInTheDocument()
})

it('shows errors and allows retrying after the service recovers', async () => {
  const base = mockApi()
  const handler = base.getMockImplementation()!
  let checks = 0
  base.mockImplementation(async (url, init) => {
    if (url.endsWith('/health/ready') && checks++ === 0) return new Response('Backend unavailable', { status: 503 })
    return handler(url, init)
  })
  renderApp()
  fireEvent.click(screen.getByText('开发环境状态'))
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 503')
  fireEvent.click(screen.getByRole('button', { name: '重新检查' }))
  expect(await screen.findByText('后端与数据库已就绪')).toBeInTheDocument()
})

it('shows login without requesting private work items for an anonymous visitor', async () => {
  const fetchMock = mockApi()
  renderApp()
  expect(await screen.findByRole('button', { name: '登录' })).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => url.includes('/work-items'))).toBe(false)
})

it('restores the session and reads work items after a fresh mount', async () => {
  const fetchMock = mockApi({ authenticated: true })
  renderApp()
  expect(await screen.findByRole('button', { name: workItem.title })).toBeInTheDocument()
  expect(screen.getByText('demo')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/auth/login'))).toBe(false)
})

it('logs in, creates a classified item and retrieves its detail', async () => {
  const fetchMock = mockApi()
  renderApp()
  await signIn()
  fillTitle('整理验收记录')
  fireEvent.change(screen.getByLabelText('紧急程度'), { target: { value: 'true' } })
  fireEvent.change(screen.getByLabelText('重要程度'), { target: { value: 'false' } })
  fireEvent.change(screen.getByLabelText('目标完成日期'), { target: { value: '2026-10-25' } })
  fireEvent.change(screen.getByLabelText('背景'), { target: { value: '周报背景' } })
  fireEvent.click(screen.getByRole('button', { name: '创建工作项' }))
  expect(await screen.findByText('工作项已创建')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByLabelText('标题')).toHaveValue(''))
  const [, request] = fetchMock.mock.calls.find(([url, init]) =>
    url.endsWith('/work-items') && init?.method === 'POST')!
  expect(JSON.parse(String(request?.body))).toMatchObject({
    title: '整理验收记录', urgency: true, importance: false, due_on: '2026-10-25', background: '周报背景',
  })
  expect(request?.headers).toMatchObject({ 'X-CSRF-Token': currentUser.csrf_token })
  expect(await screen.findByRole('heading', { name: '工作项详情' })).toBeInTheDocument()
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/work-items/2'))).toBe(true))
})

it('opens server detail and preserves date-only values', async () => {
  mockApi({ authenticated: true })
  renderApp()
  fireEvent.click(await screen.findByRole('button', { name: workItem.title }))
  const detail = await screen.findByRole('region', { name: '工作项详情' })
  expect(await within(detail).findByText('2026-10-25')).toBeInTheDocument()
  expect(within(detail).getByText(workItem.background)).toBeInTheDocument()
  expect(within(detail).getByText('待分类')).toBeInTheDocument()
})

it('shows login failures without clearing the username or pretending to authenticate', async () => {
  const fetchMock = mockApi()
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.endsWith('/auth/login')
    ? Promise.resolve(jsonResponse({ detail: 'Invalid username or password.' }, 401))
    : handler(url, init))
  renderApp()
  fireEvent.change(await screen.findByLabelText('用户名'), { target: { value: 'demo' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'wrong-password' } })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('用户名或密码错误')
  expect(screen.getByLabelText('用户名')).toHaveValue('demo')
  expect(screen.queryByRole('button', { name: '退出登录' })).not.toBeInTheDocument()
})

it('reports an unavailable session service as an error with a retry', async () => {
  const fetchMock = mockApi()
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.endsWith('/auth/me')
    ? Promise.resolve(jsonResponse({ detail: 'Service unavailable' }, 503))
    : handler(url, init))
  renderApp()
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 503')
  expect(screen.queryByRole('button', { name: '登录' })).not.toBeInTheDocument()
  fetchMock.mockImplementation(handler)
  fireEvent.click(screen.getByRole('button', { name: '重试登录态检查' }))
  expect(await screen.findByRole('button', { name: '登录' })).toBeInTheDocument()
})

it('preserves a draft on ambiguous save failure and does not auto retry', async () => {
  const fetchMock = mockApi({ authenticated: true })
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.endsWith('/work-items') && init?.method === 'POST'
    ? Promise.reject(new DOMException('Timed out', 'TimeoutError'))
    : handler(url, init))
  renderApp()
  await screen.findByRole('button', { name: '退出登录' })
  fillTitle('不能丢失的草稿')
  fireEvent.click(screen.getByRole('button', { name: '创建工作项' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('保存未确认')
  expect(screen.getByRole('alert')).toHaveTextContent('先刷新列表核对')
  expect(screen.getByLabelText('标题')).toHaveValue('不能丢失的草稿')
  expect(fetchMock.mock.calls.filter(([url, init]) =>
    url.endsWith('/work-items') && init?.method === 'POST')).toHaveLength(1)
})

it('hides private data on expiry and restores the same user draft after login', async () => {
  const fetchMock = mockApi({ authenticated: true })
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.endsWith('/work-items') && init?.method === 'POST'
    ? Promise.resolve(jsonResponse({ detail: 'Not authenticated.' }, 401))
    : handler(url, init))
  const { client } = renderApp()
  await screen.findByRole('button', { name: workItem.title })
  fillTitle('会话失效前的草稿')
  fireEvent.click(screen.getByRole('button', { name: '创建工作项' }))
  expect(await screen.findByRole('button', { name: '登录' })).toBeInTheDocument()
  expect(screen.queryByText(workItem.title)).not.toBeInTheDocument()
  expect(client.getQueriesData({ queryKey: ['work-items'] })).toHaveLength(0)
  expect(client.getMutationCache().getAll()).toHaveLength(0)
  await signIn()
  expect(screen.getByLabelText('标题')).toHaveValue('会话失效前的草稿')
})

it('clears private caches and form data after confirmed logout', async () => {
  const fetchMock = mockApi({ authenticated: true })
  const { client } = renderApp()
  await screen.findByRole('button', { name: workItem.title })
  fillTitle('退出后清除')
  fireEvent.click(screen.getByRole('button', { name: '退出登录' }))
  await screen.findByRole('button', { name: '登录' })
  expect(client.getQueriesData({ queryKey: ['work-items'] })).toHaveLength(0)
  const [, request] = fetchMock.mock.calls.find(([url]) => url.endsWith('/auth/logout'))!
  expect(request?.headers).toMatchObject({ 'X-CSRF-Token': currentUser.csrf_token })
  await signIn()
  expect(screen.getByLabelText('标题')).toHaveValue('')
})

it('keeps the workspace visible and reports a failed logout', async () => {
  const fetchMock = mockApi({ authenticated: true })
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.endsWith('/auth/logout')
    ? Promise.resolve(jsonResponse({ detail: 'CSRF validation failed.' }, 403))
    : handler(url, init))
  renderApp()
  fireEvent.click(await screen.findByRole('button', { name: '退出登录' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 403')
  expect(screen.getByRole('button', { name: '退出登录' })).toBeInTheDocument()
})

it('paginates the list without inventing a total count', async () => {
  const items = Array.from({ length: 50 }, (_, index) => ({ ...workItem, id: index + 1, title: `任务 ${index + 1}` }))
  const fetchMock = mockApi({ authenticated: true, items })
  renderApp()
  await screen.findByRole('button', { name: '任务 50' })
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  expect(await screen.findByText('本页没有工作项')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith('offset=50'))).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '上一页' }))
  expect(await screen.findByRole('button', { name: '任务 1' })).toBeInTheDocument()
})

it('reports list failures rather than claiming the workspace is empty', async () => {
  const fetchMock = mockApi({ authenticated: true })
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.includes('/work-items?')
    ? Promise.resolve(jsonResponse({ detail: 'Database unavailable' }, 503))
    : handler(url, init))
  renderApp()
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 503')
  expect(screen.queryByText('本页没有工作项')).not.toBeInTheDocument()
  fetchMock.mockImplementation(handler)
  fireEvent.click(screen.getByRole('button', { name: '刷新列表' }))
  expect(await screen.findByRole('button', { name: workItem.title })).toBeInTheDocument()
})

it('reports rejected browser cookies after a successful login response', async () => {
  const fetchMock = mockApi()
  const handler = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url, init) => url.endsWith('/auth/me')
    ? Promise.resolve(jsonResponse({ detail: 'Not authenticated.' }, 401))
    : handler(url, init))
  renderApp()
  fireEvent.change(await screen.findByLabelText('用户名'), { target: { value: 'demo' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'test-password' } })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('未能恢复会话')
  expect(screen.getByLabelText('密码')).toHaveValue('')
})

it('does not submit whitespace-only titles', async () => {
  const fetchMock = mockApi({ authenticated: true })
  renderApp()
  await screen.findByRole('button', { name: '退出登录' })
  fillTitle('   ')
  expect(screen.getByRole('button', { name: '创建工作项' })).toBeDisabled()
  expect(screen.getByRole('alert')).toHaveTextContent('标题不能只包含空白字符')
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})

it('does not expose another account’s draft after reauthentication', async () => {
  const fetchMock = mockApi({ authenticated: true })
  const handler = fetchMock.getMockImplementation()!
  const { client } = renderApp()
  await screen.findByRole('button', { name: workItem.title })
  fillTitle('账号一的私人草稿')
  await act(async () => { client.setQueryData(['auth', 'me'], null) })
  fetchMock.mockImplementation((url, init) => url.endsWith('/auth/me')
    ? Promise.resolve(jsonResponse({ ...currentUser, id: 2, username: 'second-user' }))
    : handler(url, init))
  await signIn()
  expect(screen.getByText('second-user')).toBeInTheDocument()
  expect(screen.getByLabelText('标题')).toHaveValue('')
})

it.each([401, 201])('ignores a late save response (%s) from a previous session', async (status) => {
  const fetchMock = mockApi({ authenticated: true })
  const handler = fetchMock.getMockImplementation()!
  let finishSave: (response: Response) => void = () => { throw new Error('Save has not started') }
  fetchMock.mockImplementation((url, init) => url.endsWith('/work-items') && init?.method === 'POST'
    ? new Promise<Response>(resolve => { finishSave = resolve })
    : handler(url, init))
  const { client } = renderApp()
  await screen.findByRole('button', { name: workItem.title })
  fillTitle('旧会话的保存请求')
  fireEvent.click(screen.getByRole('button', { name: '创建工作项' }))
  await waitFor(() => expect(screen.getByLabelText('标题')).toBeDisabled())
  await act(async () => { client.setQueryData(['auth', 'me'], null) })
  fetchMock.mockImplementation((url, init) => url.endsWith('/auth/me')
    ? Promise.resolve(jsonResponse({ ...currentUser, csrf_token: 'new-session-csrf' }))
    : handler(url, init))
  await signIn()
  fillTitle('新会话的草稿')
  await act(async () => {
    finishSave(status === 401
      ? jsonResponse({ detail: 'Not authenticated.' }, 401)
      : jsonResponse(workItem, 201))
  })
  expect(screen.getByRole('button', { name: '退出登录' })).toBeInTheDocument()
  expect(screen.getByLabelText('标题')).toHaveValue('新会话的草稿')
})

it.each([true, false])('does not let an earlier session check undo a confirmed auth change (login=%s)', async (signingIn) => {
  const fetchMock = mockApi({ authenticated: !signingIn })
  const handler = fetchMock.getMockImplementation()!
  const { client } = renderApp()
  if (signingIn) await screen.findByRole('button', { name: '登录' })
  else await screen.findByRole('button', { name: workItem.title })
  let finishCheck: (response: Response) => void = () => { throw new Error('Check has not started') }
  let holdNextCheck = true
  fetchMock.mockImplementation((url, init) => {
    if (url.endsWith('/auth/me') && holdNextCheck) {
      holdNextCheck = false
      return new Promise<Response>(resolve => { finishCheck = resolve })
    }
    return handler(url, init)
  })
  act(() => { void client.refetchQueries({ queryKey: ['auth', 'me'] }) })
  await waitFor(() => expect(holdNextCheck).toBe(false))
  if (signingIn) await signIn()
  else {
    fireEvent.click(screen.getByRole('button', { name: '退出登录' }))
    await screen.findByRole('button', { name: '登录' })
  }
  await act(async () => {
    finishCheck(signingIn ? jsonResponse({ detail: 'Not authenticated.' }, 401) : jsonResponse(currentUser))
  })
  expect(screen.getByRole('button', { name: signingIn ? '退出登录' : '登录' })).toBeInTheDocument()
})
