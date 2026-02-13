<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Plug,
  Copy,
  Check,
  Building2,
  Terminal,
  Info,
  KeyRound,
  AlertTriangle,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import type { APIKeyResponse } from '~/types'

const { listApiKeys } = useIamApi()
const { currentTenantId } = useApiClient()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()
const config = useRuntimeConfig()

// ── State ──────────────────────────────────────────────────────────────────

const apiKeys = ref<APIKeyResponse[]>([])
const isLoading = ref(false)
const selectedKeyId = ref<string | null>(null)
const urlCopied = ref(false)
const copiedConfigTab = ref<string | null>(null)

// ── Computed ───────────────────────────────────────────────────────────────

const apiBaseUrl = computed(() => config.public.apiBaseUrl as string)
const mcpEndpointUrl = computed(() => `${apiBaseUrl.value}/query/mcp`)
const tenantId = computed(() => currentTenantId.value ?? '<your-tenant-id>')

const activeKeys = computed(() => apiKeys.value.filter((k) => !k.is_revoked))

const selectedKey = computed(() => {
  if (!selectedKeyId.value) return null
  return activeKeys.value.find((k) => k.id === selectedKeyId.value) ?? null
})

const keyPlaceholder = computed(() => {
  if (selectedKey.value) return `${selectedKey.value.prefix}...`
  return '<YOUR_API_KEY>'
})

// ── MCP Config generators ──────────────────────────────────────────────────

function mcpConfigClaude(secret: string): string {
  return `claude mcp add kartograph-mcp --transport http ${mcpEndpointUrl.value} -H "X-API-Key: ${secret}" -H "X-Tenant-ID: ${tenantId.value}"`
}

function mcpConfigCursor(secret: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        kartograph: {
          url: mcpEndpointUrl.value,
          headers: {
            'X-API-Key': secret,
            'X-Tenant-ID': tenantId.value,
          },
        },
      },
    },
    null,
    2,
  )
}

function mcpConfigDesktop(secret: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        kartograph: {
          command: 'npx',
          args: ['-y', 'mcp-remote', mcpEndpointUrl.value],
          env: {
            X_API_KEY: secret,
            X_TENANT_ID: tenantId.value,
          },
        },
      },
    },
    null,
    2,
  )
}

function mcpConfigCurl(secret: string): string {
  return `curl -X GET ${apiBaseUrl.value}/iam/tenants \\
  -H "X-API-Key: ${secret}" \\
  -H "X-Tenant-ID: ${tenantId.value}"`
}

// ── Data fetching ──────────────────────────────────────────────────────────

async function loadKeys() {
  isLoading.value = true
  try {
    apiKeys.value = await listApiKeys()
    // Auto-select the first active key if none selected
    if (!selectedKeyId.value && activeKeys.value.length > 0) {
      selectedKeyId.value = activeKeys.value[0].id
    }
  } catch (err: unknown) {
    toast.error('Failed to load API keys', { description: extractErrorMessage(err) })
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  if (hasTenant.value) loadKeys()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    selectedKeyId.value = null
    loadKeys()
  }
})

// ── Clipboard ──────────────────────────────────────────────────────────────

async function copyToClipboard(text: string, label?: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(label ? `${label} copied to clipboard` : 'Copied to clipboard')
    return true
  } catch {
    toast.error('Failed to copy to clipboard')
    return false
  }
}

async function copyUrl() {
  const ok = await copyToClipboard(mcpEndpointUrl.value, 'MCP endpoint URL')
  if (ok) {
    urlCopied.value = true
    setTimeout(() => { urlCopied.value = false }, 2000)
  }
}

async function copyConfig(tab: string, text: string) {
  const ok = await copyToClipboard(text, `${tab} config`)
  if (ok) {
    copiedConfigTab.value = tab
    setTimeout(() => { copiedConfigTab.value = null }, 2000)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <Plug class="size-6 text-muted-foreground" />
      <div>
        <h1 class="text-2xl font-bold tracking-tight">MCP Integration</h1>
        <p class="text-sm text-muted-foreground">
          Connect AI agents to your knowledge graph via the Model Context Protocol
        </p>
      </div>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view MCP integration details.</p>
    </div>

    <template v-else>
      <!-- B. Endpoint Info Card -->
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Endpoint Information</CardTitle>
          <CardDescription>Use this endpoint to connect your MCP-compatible tools</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-3">
            <div class="flex items-center justify-between gap-2">
              <div class="space-y-1">
                <p class="text-sm font-medium">MCP Endpoint URL</p>
                <code class="block rounded-md border bg-muted px-3 py-2 font-mono text-sm break-all">
                  {{ mcpEndpointUrl }}
                </code>
              </div>
              <Button variant="outline" size="icon" class="shrink-0" @click="copyUrl">
                <component :is="urlCopied ? Check : Copy" class="size-4" />
              </Button>
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div class="space-y-1">
                <p class="text-xs font-medium text-muted-foreground">Transport</p>
                <Badge variant="secondary">Streamable HTTP</Badge>
              </div>
              <div class="space-y-1">
                <p class="text-xs font-medium text-muted-foreground">Authentication</p>
                <Badge variant="secondary">API Key + Tenant ID</Badge>
              </div>
              <div class="space-y-1">
                <p class="text-xs font-medium text-muted-foreground">Headers</p>
                <div class="flex flex-wrap gap-1">
                  <Badge variant="outline">X-API-Key</Badge>
                  <Badge variant="outline">X-Tenant-ID</Badge>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- C. Available Tools -->
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Available Tools</CardTitle>
          <CardDescription>MCP tools exposed by the Kartograph server</CardDescription>
        </CardHeader>
        <CardContent>
          <div class="rounded-md border p-4 space-y-3">
            <div class="flex items-center gap-2">
              <Terminal class="size-4 text-muted-foreground" />
              <code class="text-sm font-semibold">query_graph</code>
            </div>
            <p class="text-sm text-muted-foreground">
              Execute Cypher queries against the knowledge graph.
            </p>
            <div class="space-y-2">
              <p class="text-xs font-medium text-muted-foreground uppercase tracking-wider">Parameters</p>
              <div class="space-y-1.5 text-sm">
                <div class="flex items-start gap-2">
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">cypher</code>
                  <span class="text-muted-foreground">string</span>
                  <Badge variant="default" class="text-[10px] px-1.5 py-0">required</Badge>
                </div>
                <div class="flex items-start gap-2">
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">timeout_seconds</code>
                  <span class="text-muted-foreground">number</span>
                  <Badge variant="secondary" class="text-[10px] px-1.5 py-0">optional</Badge>
                </div>
                <div class="flex items-start gap-2">
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">max_rows</code>
                  <span class="text-muted-foreground">number</span>
                  <Badge variant="secondary" class="text-[10px] px-1.5 py-0">optional</Badge>
                </div>
              </div>
              <p class="text-xs text-muted-foreground">
                Returns query results as JSON.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- D. Connection Configs -->
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Connection Configuration</CardTitle>
          <CardDescription>
            Select an API key and copy the configuration for your preferred tool
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- API Key selector -->
          <div v-if="activeKeys.length > 0" class="space-y-2">
            <div class="flex items-center gap-2">
              <KeyRound class="size-4 text-muted-foreground" />
              <span class="text-sm font-medium">API Key</span>
            </div>
            <Select v-model="selectedKeyId">
              <SelectTrigger class="w-full sm:w-80">
                <SelectValue placeholder="Select an API key..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="key in activeKeys"
                  :key="key.id"
                  :value="key.id"
                >
                  {{ key.name }} ({{ key.prefix }}...)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- No keys CTA -->
          <Alert v-else-if="!isLoading">
            <Info class="size-4" />
            <AlertDescription class="flex items-center justify-between gap-2">
              <span>No API keys found. Create one to generate connection configs.</span>
              <NuxtLink to="/api-keys">
                <Button size="sm" variant="outline">Create API Key</Button>
              </NuxtLink>
            </AlertDescription>
          </Alert>

          <Alert v-if="activeKeys.length > 0">
            <AlertTriangle class="size-4" />
            <AlertDescription>
              The full API key secret is only shown at creation time. The configs below
              use a placeholder — replace <code class="font-mono text-xs">&lt;YOUR_API_KEY&gt;</code> with
              your actual secret.
            </AlertDescription>
          </Alert>

          <!-- Config tabs -->
          <div v-if="activeKeys.length > 0" class="space-y-3">
            <Tabs default-value="claude-code" class="w-full">
              <TabsList class="grid w-full grid-cols-4">
                <TabsTrigger value="claude-code">Claude Code</TabsTrigger>
                <TabsTrigger value="cursor">Cursor</TabsTrigger>
                <TabsTrigger value="claude-desktop">Claude Desktop</TabsTrigger>
                <TabsTrigger value="curl">cURL</TabsTrigger>
              </TabsList>

              <!-- Claude Code -->
              <TabsContent value="claude-code" class="space-y-3">
                <p class="text-sm text-muted-foreground">
                  Run this command in your terminal to add Kartograph as an MCP server:
                </p>
                <div class="relative">
                  <pre class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground">{{ mcpConfigClaude(keyPlaceholder) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('Claude Code', mcpConfigClaude(keyPlaceholder))"
                  >
                    <component :is="copiedConfigTab === 'Claude Code' ? Check : Copy" class="size-4" />
                  </Button>
                </div>
              </TabsContent>

              <!-- Cursor -->
              <TabsContent value="cursor" class="space-y-3">
                <p class="text-sm text-muted-foreground">
                  Add this to your <code class="rounded bg-muted px-1 py-0.5 font-mono text-xs">.cursor/mcp.json</code> file:
                </p>
                <div class="relative">
                  <pre class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground">{{ mcpConfigCursor(keyPlaceholder) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('Cursor', mcpConfigCursor(keyPlaceholder))"
                  >
                    <component :is="copiedConfigTab === 'Cursor' ? Check : Copy" class="size-4" />
                  </Button>
                </div>
              </TabsContent>

              <!-- Claude Desktop -->
              <TabsContent value="claude-desktop" class="space-y-3">
                <p class="text-sm text-muted-foreground">
                  Add this to your <code class="rounded bg-muted px-1 py-0.5 font-mono text-xs">claude_desktop_config.json</code> file:
                </p>
                <div class="relative">
                  <pre class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground">{{ mcpConfigDesktop(keyPlaceholder) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('Claude Desktop', mcpConfigDesktop(keyPlaceholder))"
                  >
                    <component :is="copiedConfigTab === 'Claude Desktop' ? Check : Copy" class="size-4" />
                  </Button>
                </div>
              </TabsContent>

              <!-- cURL -->
              <TabsContent value="curl" class="space-y-3">
                <p class="text-sm text-muted-foreground">
                  Test your API key with a simple cURL request:
                </p>
                <div class="relative">
                  <pre class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground">{{ mcpConfigCurl(keyPlaceholder) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('cURL', mcpConfigCurl(keyPlaceholder))"
                  >
                    <component :is="copiedConfigTab === 'cURL' ? Check : Copy" class="size-4" />
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
