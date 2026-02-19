// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from '@tailwindcss/vite'

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
