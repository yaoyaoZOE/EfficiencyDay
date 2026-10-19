import { useQuery } from '@tanstack/react-query'
import { fetchReadiness } from './api/health'

export default function App() {
  const health = useQuery({
    queryKey: ['health', 'ready'],
    queryFn: ({ signal }) => fetchReadiness(signal),
    retry: false,
    staleTime: 30_000,
  })

  return (
    <main className="shell">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">E</span>
        <span>EfficiencyDay</span>
        <span className="badge">开发骨架</span>
      </header>

      <section className="intro">
        <p className="eyebrow">PLAN · FOCUS · REVIEW</p>
        <h1>从清晰记录，开始高效的一天。</h1>
        <p>前后端与数据库连接检查。工作项管理功能将在此基础上逐步构建。</p>
      </section>

      <section className="card" aria-labelledby="status-title">
        <div className="card-heading">
          <h2 id="status-title">开发环境状态</h2>
          <button
            type="button"
            disabled={health.isFetching}
            onClick={() => { void health.refetch() }}
          >
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
      </section>

      <footer>仅供本地开发 · 尚未开放登录和任务管理功能</footer>
    </main>
  )
}
