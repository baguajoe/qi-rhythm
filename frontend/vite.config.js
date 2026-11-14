import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Qi Rhythm',
        short_name: 'Qi Rhythm',
        description: 'Instructor-led rhythm and team games for senior centers.',
        theme_color: '#1b3a5c',
        background_color: '#fdfaf3',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            // Cache the rhythm library so it works offline
            urlPattern: ({ url }) =>
              url.pathname.startsWith('/api/genres') || url.pathname.startsWith('/api/rhythms'),
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'rhythm-library' },
          },
        ],
      },
    }),
  ],
  server: { port: 5173, host: true },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
});
