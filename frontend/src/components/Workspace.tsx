import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createWorkItem, fetchWorkItem, fetchWorkItems, logout } from '../api/client'
import type { CurrentUser, WorkItemCreate } from '../api/client'
import { ApiError } from '../api/http'
import { emptyDraft, WorkItemForm } from './WorkItemForm'
import type { WorkItemDraft } from './WorkItemForm'
import { classification, statusLabels, WorkItemDetail } from './WorkItemDetail'

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

interface Props {
  user: CurrentUser
  draft: WorkItemDraft
  onDraftChange: (draft: WorkItemDraft) => void
  onExpired: (expected: CurrentUser) => void
  onLogout: (expected: CurrentUser) => void
}

export function Workspace({ user, draft, onDraftChange, onExpired, onLogout }: Props) {
  const client = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const list = useQuery({
    queryKey: ['work-items', user.id, 'list', offset],
    queryFn: ({ signal }) => fetchWorkItems(50, offset, signal),
    retry: false,
  })
  const detail = useQuery({
    queryKey: ['work-items', user.id, 'detail', selectedId],
    queryFn: ({ signal }) => {
      if (selectedId === null) throw new Error('No work item selected.')
      return fetchWorkItem(selectedId, signal)
    },
    enabled: selectedId !== null,
    retry: false,
  })
  useEffect(() => {
    if (isUnauthorized(list.error) || isUnauthorized(detail.error)) onExpired(user)
  }, [list.error, detail.error, onExpired, user])

  const create = useMutation({
    retry: false,
    mutationFn: (payload: WorkItemCreate) => createWorkItem(payload, user.csrf_token),
    onSuccess: item => {
      onDraftChange(emptyDraft)
      setOffset(0)
      setSelectedId(item.id)
      void client.invalidateQueries({ queryKey: ['work-items', user.id, 'list'] })
    },
    onError: error => { if (isUnauthorized(error)) onExpired(user) },
  })
  const exit = useMutation({
    retry: false,
    mutationFn: () => logout(user.csrf_token),
    onSuccess: () => onLogout(user),
    onError: error => { if (isUnauthorized(error)) onExpired(user) },
  })
  const changePage = (newOffset: number) => {
    setSelectedId(null)
    setOffset(newOffset)
  }
  const createError = create.isError ? (
    create.error instanceof ApiError && create.error.status >= 400 && create.error.status < 500
      ? `创建失败，输入已保留。${create.error.message}`
      : `保存未确认，输入已保留。请先刷新列表核对，避免重复创建。${create.error.message}`
  ) : null

  return (
    <>
      <div className="workspace-heading">
        <div><h1>个人工作台</h1><p className="muted">把今天的想法，变成清晰的行动。</p></div>
        <div className="account">
          <span>{user.username}</span>
          <button type="button" disabled={exit.isPending || create.isPending}
            onClick={() => exit.mutate()}>{exit.isPending ? '正在退出…' : '退出登录'}</button>
        </div>
      </div>
      {exit.isError && !isUnauthorized(exit.error) && (
        <p role="alert" className="error">退出未确认，请重试。{exit.error.message}</p>
      )}
      <div className="workspace-grid">
        <div className="stack">
          <section className="card" aria-labelledby="list-title">
            <div className="card-heading">
              <h2 id="list-title">我的工作项</h2>
              <button type="button" disabled={list.isFetching} onClick={() => { void list.refetch() }}>刷新列表</button>
            </div>
            <p className="muted">按录入时间倒序 · 每页最多 50 条</p>
            {list.isPending ? <p role="status">正在读取工作项…</p> : list.isError ? (
              <p role="alert" className="error">读取失败，请刷新列表重试。{list.error.message}</p>
            ) : list.data.items.length === 0 ? (
              <p className="empty">本页没有工作项</p>
            ) : (
              <ul className="work-items">
                {list.data.items.map(item => (
                  <li key={item.id} className={selectedId === item.id ? 'selected' : undefined}>
                    <button type="button" className="item-title" aria-pressed={selectedId === item.id}
                      onClick={() => setSelectedId(item.id)}>{item.title}</button>
                    <div className="item-meta">
                      <span className="badge">{statusLabels[item.status]}</span>
                      <span>{classification(item)}</span>
                      {item.due_on && <span>目标 {item.due_on}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <nav className="pagination" aria-label="工作项分页">
              <button type="button" disabled={offset === 0 || list.isFetching}
                onClick={() => changePage(Math.max(0, offset - 50))}>上一页</button>
              <span>第 {offset / 50 + 1} 页</span>
              <button type="button" disabled={list.isFetching || list.isError || !list.data || list.data.items.length < 50}
                onClick={() => changePage(offset + 50)}>下一页</button>
            </nav>
          </section>
          {selectedId !== null && (
            <section className="card" aria-labelledby="detail-title">
              <div className="card-heading">
                <h2 id="detail-title">工作项详情</h2>
                <button type="button" onClick={() => setSelectedId(null)}>关闭详情</button>
              </div>
              {detail.isPending ? <p role="status">正在读取详情…</p> : detail.isError ? (
                <div role="alert" className="error">
                  <p>详情读取失败。{detail.error.message}</p>
                  <button type="button" disabled={detail.isFetching} onClick={() => { void detail.refetch() }}>重试详情</button>
                </div>
              ) : detail.data ? <WorkItemDetail item={detail.data} timezone={user.timezone} /> : null}
            </section>
          )}
        </div>
        <WorkItemForm draft={draft} onChange={value => {
          create.reset()
          onDraftChange(value)
        }} onSubmit={payload => create.mutate(payload)} busy={create.isPending || exit.isPending}
          error={createError} created={create.isSuccess} />
      </div>
    </>
  )
}
