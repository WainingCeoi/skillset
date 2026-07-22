import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to the FastAPI backend, so the frontend calls same-origin
// (/api/...) and EventSource/SSE works without CORS in dev. `host: '127.0.0.1'` avoids Vite
// binding IPv6-only ([::1]), which some in-app / headless browsers can't reach.
//
// Keep this file as `vite.config.ts` (the `react-ts` template's default): `defineConfig` then
// type-checks the config itself, so a typo'd option is a build error rather than a silently
// ignored key.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // <-- your backend port
        changeOrigin: true,
      },
    },
  },
})
