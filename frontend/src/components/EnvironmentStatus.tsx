import { useQuery } from '@tanstack/react-query'
import { fetchReadiness } from '../api/health'

export function EnvironmentStatus() {
  const health = useQuery({
    queryKey: ['health', 'ready'],
    queryFn: ({ signal }) => fetchReadiness(signal),
    retry: false,
    staleTime: 30_000,
  })

  return (
    <details className="card environment">
      <summary>开发环境状态</summary>
      <div className="card-heading">
        <h2>连接检查</h2>
        <button type="button" disabled={health.isFetching} onClick={() => { void health.refetch() }}>
          重新检查
        </button>
      </div>
      {health.isFetching ? (
        <p role="status" className="status">正在检查后端与数据库连接…</p>
      ) : health.isError ? (
        <div role="alert" className="error">
          <strong>连接检查失败</strong>
          <p>{health.error.message}</p>
          <p>请确认后端已启动，并已执行数据库迁移。检查后可重新尝试。</p>
        </div>
      ) : (
        <p role="status" className="status success">后端与数据库已就绪</p>
      )}
      <dl className="endpoints">
        <div><dt>前端开发服务</dt><dd>127.0.0.1:8327</dd></div>
        <div><dt>后端 API</dt><dd>127.0.0.1:6931</dd></div>
        <div><dt>数据存储</dt><dd>SQLite · SQLAlchemy · Alembic</dd></div>
      </dl>
      <a href="http://127.0.0.1:6931/docs" target="_blank" rel="noreferrer">
        打开 FastAPI 接口文档 →
      </a>
    </details>
  )
}
