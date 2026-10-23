import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { fetchCurrentUser, login } from '../api/client'
import type { CurrentUser } from '../api/client'
import { ApiError } from '../api/http'

export function LoginForm({ onLogin }: { onLogin: (user: CurrentUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    retry: false,
    mutationFn: async () => {
      try {
        await login(username, password)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          throw new Error('用户名或密码错误，请重新输入。')
        }
        throw error
      }
      setPassword('')
      try {
        return await fetchCurrentUser()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          throw new Error('登录请求已成功，但未能恢复会话。请使用本机回环地址或 HTTPS，并确认浏览器允许 Cookie。')
        }
        throw error
      }
    },
    onSuccess: onLogin,
  })

  return (
    <section className="card login-card" aria-labelledby="login-title">
      <h2 id="login-title">登录个人工作台</h2>
      <p className="muted">使用已配置的个人账号登录。暂不开放注册。</p>
      <form onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
        <fieldset disabled={mutation.isPending}>
          <label htmlFor="username">用户名</label>
          <input id="username" name="username" autoComplete="username" required
            value={username} onChange={event => setUsername(event.target.value)} />
          <label htmlFor="password">密码</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required
            value={password} onChange={event => setPassword(event.target.value)} />
          <button className="primary" type="submit">{mutation.isPending ? '正在登录…' : '登录'}</button>
        </fieldset>
        {mutation.isError && <p role="alert" className="error">{mutation.error.message}</p>}
      </form>
    </section>
  )
}
