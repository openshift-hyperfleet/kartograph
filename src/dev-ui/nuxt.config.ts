// https://nuxt.com/docs/api/configuration/nuxt-config
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'

function readVersion(): string {
  try {
    const raw = readFileSync(resolve(__dirname, 'VERSION'), 'utf-8')
    const version = raw.split('#')[0].trim()
    return version || process.env.APP_VERSION || 'dev'
  } catch {
    return process.env.APP_VERSION || 'dev'
  }
}

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: process.env.NODE_ENV !== 'production' },
  ssr: false,
  vite: {
    plugins: [tailwindcss()],
  },
  css: ['~/assets/css/main.css', 'vue-sonner/style.css'],
  imports: {
    dirs: ['composables/api'],
  },
  runtimeConfig: {
    public: {
      appVersion: readVersion(),
      apiBaseUrl: 'http://localhost:8000',
      mcpEndpointUrl: 'http://localhost:8000/query/mcp',
      keycloak: {
        url: 'http://localhost:8080',
        realm: 'kartograph',
        clientId: 'kartograph-ui',
      },
    },
  },
})
