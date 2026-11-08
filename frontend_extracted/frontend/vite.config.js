import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The UI talks to the API through /api on its own origin, so the browser
// treats the session cookies as first-party (no cross-site cookie problems
// between localhost:5173 and 127.0.0.1:8000). The proxy strips /api and tells
// the backend about the prefix, so the refresh cookie gets Path=/api/auth.
// Docker's nginx does the same (Dockerfile.frontend).
const API_TARGET = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: false,   // keep the browser's Origin, checked by the backend's CSRF guard
        rewrite: (path) => path.replace(/^\/api/, ''),
        headers: { 'X-Forwarded-Prefix': '/api' },
      },
    },
  },
})
