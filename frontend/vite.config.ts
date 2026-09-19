import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const apiUrl = process.env.VITE_API_URL

if (!apiUrl) {
  throw new Error('VITE_API_URL is required')
}

export default defineConfig({
  plugins: [react(), tailwindcss(), viteStaticCopy({
    targets: ['cmaps', 'wasm', 'iccs', 'standard_fonts'].map(directory => ({
      src: `node_modules/pdfjs-dist/${directory}`,
      dest: 'pdfjs',
    })),
  })],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: ['macbook-pro.taila153f0.ts.net'],
    proxy: {
      '/api': {
        target: apiUrl,
        changeOrigin: true,
        xfwd: true,
      },
    },
  },
})
