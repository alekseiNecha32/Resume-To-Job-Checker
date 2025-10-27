import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward all API requests to Flask backend
      '/api': {
        target: 'http://127.0.0.1:5000', // or 5232 if that's the Flask port
        changeOrigin: true,
      },
    },
  },
})