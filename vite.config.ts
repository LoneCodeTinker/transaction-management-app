import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allow LAN access
    port: 5174,
    strictPort: true,
    // HMR configuration for external domain access
    hmr: {
      host: 'mc.mrmemon.uk',
      port: 5174,
      protocol: 'http'
    },
    proxy: {
      // Proxy API requests to FastAPI backend
      '/transaction': 'http://localhost:8001',
      '/transactions': 'http://localhost:8001',
      '/orders': 'http://localhost:8001',
      '/clients': 'http://localhost:8001',
    },
    allowedHosts: ['mc.mrmemon.uk', 'localhost', '127.0.0.1'],
  },
});
