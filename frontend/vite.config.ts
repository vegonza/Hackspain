import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

const apiUrl = process.env.VITE_API_URL

if (!apiUrl) {
  throw new Error('VITE_API_URL is required')
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: apiUrl,
        changeOrigin: true,
        xfwd: true,
      },
    },
  },
})
