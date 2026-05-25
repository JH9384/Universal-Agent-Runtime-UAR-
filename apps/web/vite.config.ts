import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // Three.js is a deliberate lazy-loaded graphics dependency. Keep the
    // warning threshold tight enough that unexpected app growth still shows.
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react')) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/@react-three/drei')) {
            return 'vendor-three-drei'
          }
          if (id.includes('node_modules/@react-three/fiber')) {
            return 'vendor-three-fiber'
          }
          if (id.includes('node_modules/three')) {
            return 'vendor-three-core'
          }
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
