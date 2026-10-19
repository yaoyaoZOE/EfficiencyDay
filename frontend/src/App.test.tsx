import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import App from './App'

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

it('shows real backend and database readiness', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ status: 'ok', database: 'ok' })),
  ))
  renderApp()
  expect(screen.getByRole('status')).toHaveTextContent('正在检查')
  expect(await screen.findByText('后端与数据库已就绪')).toBeInTheDocument()
})

it('shows errors and allows retrying after the service recovers', async () => {
  vi.stubGlobal('fetch', vi.fn()
    .mockResolvedValueOnce(new Response('Backend unavailable', { status: 503 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok', database: 'ok' })),
    ))
  renderApp()
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 503')
  fireEvent.click(screen.getByRole('button', { name: '重新检查' }))
  expect(await screen.findByText('后端与数据库已就绪')).toBeInTheDocument()
})
