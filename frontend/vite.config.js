import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: 'localhost',
    port: 3000,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
      '/health': 'http://127.0.0.1:8010',
      '/docs': 'http://127.0.0.1:8010',
      '/openapi.json': 'http://127.0.0.1:8010',
    },
  },
})
