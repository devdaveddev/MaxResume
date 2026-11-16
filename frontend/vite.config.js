import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the React app runs on :5173 and proxies API calls to FastAPI on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.API_URL || 'http://localhost:8000', changeOrigin: true } },
  },
})
