import { useCallback, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCurrentUser } from './api/client'
import type { CurrentUser } from './api/client'
import { EnvironmentStatus } from './components/EnvironmentStatus'
import { LoginForm } from './components/LoginForm'
import { isUnauthorized, Workspace } from './components/Workspace'
import { emptyDraft } from './components/WorkItemForm'
import type { WorkItemDraft } from './components/WorkItemForm'

export default function App() {
  const client = useQueryClient()
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState<{ ownerId: number | null; value: WorkItemDraft }>({
    ownerId: null, value: emptyDraft,
  })
  const auth = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async ({ signal }) => {
      try {
        return await fetchCurrentUser(signal)
      } catch (error) {
        if (isUnauthorized(error)) return null
        throw error
      }
    },
    retry: false,
  })
  const clearPrivateState = useCallback(() => {
    void client.cancelQueries({ queryKey: ['auth', 'me'] })
    void client.cancelQueries({ queryKey: ['work-items'] })
    client.removeQueries({ queryKey: ['work-items'] })
    client.getMutationCache().clear()
  }, [client])
  useEffect(() => {
    if (auth.data === null) clearPrivateState()
  }, [auth.data, clearPrivateState])
  const isCurrentSession = useCallback((expected: CurrentUser) => {
    const active = client.getQueryData<CurrentUser | null>(['auth', 'me'])
    return active?.id === expected.id && active.csrf_token === expected.csrf_token
  }, [client])
  const expire = useCallback((expected: CurrentUser) => {
    if (!isCurrentSession(expected)) return
    clearPrivateState()
    client.setQueryData(['auth', 'me'], null)
    setNotice('登录已失效，请重新登录。同一账号重新登录后可继续当前页面的草稿。')
  }, [client, clearPrivateState, isCurrentSession])
  const onLogin = (user: CurrentUser) => {
    clearPrivateState()
    if (draft.ownerId !== user.id) setDraft({ ownerId: user.id, value: emptyDraft })
    setNotice('')
    client.setQueryData(['auth', 'me'], user)
  }
  const onLogout = (expected: CurrentUser) => {
    if (!isCurrentSession(expected)) return
    clearPrivateState()
    setDraft({ ownerId: null, value: emptyDraft })
    setNotice('已退出登录。')
    client.setQueryData(['auth', 'me'], null)
  }
  const user = auth.data
  return (
    <main className="shell">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">E</span>
        <span>EfficiencyDay</span>
        <span className="badge">个人工作项</span>
      </header>
      {notice && <p role="status" className="status">{notice}</p>}
      {auth.isPending ? <p role="status" className="status">正在检查登录状态…</p> : auth.isError ? (
        <section className="card">
          <p role="alert" className="error">登录态检查失败。{auth.error.message}</p>
          <button type="button" disabled={auth.isFetching} onClick={() => { void auth.refetch() }}>重试登录态检查</button>
        </section>
      ) : user ? (
        <Workspace key={user.csrf_token} user={user}
          draft={draft.ownerId === user.id ? draft.value : emptyDraft}
          onDraftChange={value => {
            if (isCurrentSession(user)) setDraft({ ownerId: user.id, value })
          }}
          onExpired={expire} onLogout={onLogout} />
      ) : (
        <>
          <section className="intro">
            <p className="eyebrow">PLAN · FOCUS · REVIEW</p>
            <h1>从清晰记录，开始高效的一天。</h1>
            <p>登录后记录工作项，明确目标与优先级，让每一次行动都有迹可循。</p>
          </section>
          <LoginForm onLogin={onLogin} />
        </>
      )}
      <EnvironmentStatus />
      <footer>本地开发版本 · 已接入登录、创建与读取 · 编辑及状态流转尚未开放</footer>
    </main>
  )
}
