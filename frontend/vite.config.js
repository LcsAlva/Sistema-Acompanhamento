import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5176,
    proxy: {
      '/api': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        timeout: 300_000,                 // suporta upload longo da EAP
      }
    }
  },
  build: {
    outDir: 'dist'
  }
})
