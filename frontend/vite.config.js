import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/Nexus_core/',  // This is critical for GitHub Pages!
  server: {
    port: 5173
  }
})
