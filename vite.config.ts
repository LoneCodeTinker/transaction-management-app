import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allow LAN access
    port: 5173,
    strictPort: true,
    proxy: {
      // Proxy API requests to FastAPI backend
      '/transaction': 'http://localhost:8000',
      '/transactions': 'http://localhost:8000',
    },
    allowedHosts: ['mc-nas.ddns.net'],
  },
});
