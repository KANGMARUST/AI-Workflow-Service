import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiPrefix = (env.VITE_API_PREFIX || '/api').startsWith('/')
    ? (env.VITE_API_PREFIX || '/api')
    : `/${env.VITE_API_PREFIX}`;

  return {
    plugins: [react()],
    server: {
      proxy: {
        [apiPrefix]: {
          target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
