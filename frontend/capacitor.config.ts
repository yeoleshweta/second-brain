import type { CapacitorConfig } from '@capacitor/cli'

const isCloud = !!process.env.CAPACITOR_SERVER_URL

const config: CapacitorConfig = {
  appId: 'com.secondbrain.centralperk',
  appName: 'Central Perk',
  webDir: 'dist',

  // In dev: live-reload from the running Vite dev server.
  // In production build: leave undefined so the bundled dist/ is used.
  ...(process.env.CAPACITOR_SERVER_URL
    ? { server: { url: process.env.CAPACITOR_SERVER_URL, cleartext: true } }
    : {}),

  ios: {
    contentInset: 'automatic',
    scrollEnabled: false,          // React handles scrolling
    backgroundColor: '#FAF0E4',
    preferredContentMode: 'mobile',
  },
  android: {
    backgroundColor: '#FAF0E4',
    captureInput: true,
  },
  plugins: {
    StatusBar: {
      style: 'DARK',              // dark text on the perk-cream background
      backgroundColor: '#FAF0E4',
      overlaysWebView: false,
    },
    Keyboard: {
      resize: 'body',             // keeps chat input above keyboard
      resizeOnFullScreen: true,
    },
  },
}

export default config
