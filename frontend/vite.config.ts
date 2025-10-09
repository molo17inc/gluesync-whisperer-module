import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  build: {
    rollupOptions: {
      onwarn(warning, warn) {
        // Suppress TypeScript errors during build
        if (warning.code === 'TS_ERROR') return
        warn(warning)
      }
    }
  }
})
