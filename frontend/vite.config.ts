import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // During dev, the service worker is active so offline shell works
      devOptions: { enabled: true },
      includeAssets: ['icons/void-touch-icon.png', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-maskable.png', 'logo.svg'],
      // What the service worker pre-caches at install time
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Runtime cache for API calls — network-first, fall back to cache
        runtimeCaching: [
          {
            urlPattern: /^http.*\/api\/health/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache-v2',
              expiration: { maxEntries: 50, maxAgeSeconds: 300 },
              networkTimeoutSeconds: 5,
            },
          },
        ],
        // Don't try to precache large blobs from Vite dev
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
      },
      manifest: {
        id: '/',
        name: 'The Void',
        short_name: 'The Void',
        description: 'One chat. Say remember this, and it stays.',
        start_url: '/?source=pwa',
        display: 'standalone',
        background_color: '#0B0B10',
        theme_color: '#0B0B10',
        orientation: 'portrait-primary',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/icons/icon-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
