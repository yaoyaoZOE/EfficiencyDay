import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 8327,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:6931',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 8327,
    strictPort: true,
  },
  test: {
    pool: 'threads',
    maxWorkers: 1,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
