<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import {
  Plug,
  Copy,
  Check,
  Building2,
  Terminal,
  Info,
  KeyRound,
  ChevronDown,
  Plus,
  Loader2,
  CircleCheck,
  Zap,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

import type { APIKeyResponse, APIKeyCreatedResponse } from '~/types'

const { createApiKey, listApiKeys } = useIamApi()
const { currentTenantId } = useApiClient()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()
const transientSecret = useTransientSecret()
const config = useRuntimeConfig()

// ── State ──────────────────────────────────────────────────────────────────

const apiKeys = ref<APIKeyResponse[]>([])
const isLoading = ref(false)
const copiedConfigTab = ref<string | null>(null)
const showDetails = ref(false)
const showTools = ref(false)

// Inline API key creation
const createDialogOpen = ref(false)
const createForm = reactive({ name: '', expires_in_days: 30 })
const isCreating = ref(false)
const createExpiryError = ref('')
const newlyCreatedKey = ref<APIKeyCreatedResponse | null>(null)
const secretCopied = ref(false)

// Copy feedback for endpoint URL
const endpointCopied = ref(false)

// Copy feedback for header values
const copiedHeader = ref<string | null>(null)

// ── Computed ───────────────────────────────────────────────────────────────

const apiBaseUrl = computed(() => config.public.apiBaseUrl as string)
const mcpEndpointUrl = computed(() => `${apiBaseUrl.value}/query/mcp`)
const tenantId = computed(() => currentTenantId.value ?? '<your-tenant-id>')

const activeKeys = computed(() => apiKeys.value.filter((k) => !k.is_revoked))

// Determine what secret to use in config blocks:
// Only show a real secret when we actually have one (just created).
// Otherwise show an obvious placeholder — never a truncated prefix.
const configSecret = computed(() => {
  if (newlyCreatedKey.value) return newlyCreatedKey.value.secret
  return '<YOUR_API_KEY>'
})

const hasRealSecret = computed(() => !!newlyCreatedKey.value)

const configReady = computed(() => hasTenant.value && hasRealSecret.value)

// ── MCP Config generators ──────────────────────────────────────────────────

// Display version: multiline with \ continuations for readability
function mcpConfigClaudeDisplay(secret: string): string {
  return [
    'claude mcp add kartograph-mcp \\',
    '  --transport http \\',
    `  ${mcpEndpointUrl.value} \\`,
    `  -H "X-API-Key: ${secret}" \\`,
    `  -H "X-Tenant-ID: ${tenantId.value}"`,
  ].join('\n')
}

// Copy version: single line for clipboard
function mcpConfigClaudeCopy(secret: string): string {
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

// Display version: multiline with \ continuations
function mcpConfigCurlDisplay(secret: string): string {
  return [
    `curl -X GET ${apiBaseUrl.value}/iam/tenants \\`,
    `  -H "X-API-Key: ${secret}" \\`,
    `  -H "X-Tenant-ID: ${tenantId.value}"`,
  ].join('\n')
}

// Copy version: single line for clipboard
function mcpConfigCurlCopy(secret: string): string {
  return `curl -X GET ${apiBaseUrl.value}/iam/tenants -H "X-API-Key: ${secret}" -H "X-Tenant-ID: ${tenantId.value}"`
}

// ── Data fetching ──────────────────────────────────────────────────────────

async function loadKeys() {
  isLoading.value = true
  try {
    apiKeys.value = await listApiKeys()
  } catch (err: unknown) {
    toast.error('Failed to load API keys', { description: extractErrorMessage(err) })
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  // If a secret was passed from the API Keys page, consume it and
  // populate newlyCreatedKey so the config blocks show the real secret.
  const transferred = transientSecret.consume()
  if (transferred) {
    // Build a synthetic APIKeyCreatedResponse with the fields the
    // template actually uses (name + secret). The remaining fields
    // are placeholders — they are not rendered on this page.
    newlyCreatedKey.value = {
      id: '',
      name: transferred.keyName ?? 'Transferred Key',
      prefix: '',
      created_by_user_id: '',
      created_at: new Date().toISOString(),
      expires_at: new Date().toISOString(),
      last_used_at: null,
      is_revoked: false,
      secret: transferred.secret,
    }
  }

  if (hasTenant.value) loadKeys()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    newlyCreatedKey.value = null
    secretCopied.value = false
    loadKeys()
  }
})

// ── Inline API Key Creation ────────────────────────────────────────────────

async function handleCreateKey() {
  if (!createForm.name.trim()) {
    toast.error('Key name is required')
    return
  }
  if (createForm.expires_in_days < 1 || createForm.expires_in_days > 3650) {
    createExpiryError.value = 'Must be between 1 and 3650 days'
    return
  }
  createExpiryError.value = ''
  isCreating.value = true
  try {
    const key = await createApiKey({
      name: createForm.name.trim(),
      expires_in_days: createForm.expires_in_days,
    })
    newlyCreatedKey.value = key
    createForm.name = ''
    createForm.expires_in_days = 30
    secretCopied.value = false
    toast.success(`API key "${key.name}" created`)
    await loadKeys()
  } catch (err: unknown) {
    toast.error('Failed to create API key', {
      description: extractErrorMessage(err),
    })
  } finally {
    createDialogOpen.value = false
    isCreating.value = false
  }
}

// ── Clipboard ──────────────────────────────────────────────────────────────

async function copyToClipboard(text: string, label?: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(label ? `${label} copied` : 'Copied to clipboard')
    return true
  } catch {
    toast.error('Failed to copy to clipboard')
    return false
  }
}

async function copyConfig(tab: string, text: string) {
  const ok = await copyToClipboard(text, `${tab} config`)
  if (ok) {
    copiedConfigTab.value = tab
    setTimeout(() => { copiedConfigTab.value = null }, 2000)
  }
}

async function copySecret() {
  if (!newlyCreatedKey.value) return
  const ok = await copyToClipboard(newlyCreatedKey.value.secret, 'API key secret')
  if (ok) secretCopied.value = true
}

async function copyEndpoint() {
  const ok = await copyToClipboard(mcpEndpointUrl.value, 'MCP endpoint URL')
  if (ok) {
    endpointCopied.value = true
    setTimeout(() => { endpointCopied.value = false }, 2000)
  }
}

async function copyHeaderValue(key: string, value: string) {
  const ok = await copyToClipboard(value, key)
  if (ok) {
    copiedHeader.value = key
    setTimeout(() => { copiedHeader.value = null }, 2000)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <div class="rounded-lg bg-primary/10 p-2">
        <Plug class="size-5 text-primary" />
      </div>
      <div>
        <h1 class="text-2xl font-bold tracking-tight">MCP Integration</h1>
        <p class="text-sm text-muted-foreground">
          Connect AI agents to your knowledge graph via the Model Context Protocol.
        </p>
      </div>
    </div>

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view MCP integration details.</p>
    </div>

    <template v-else>
      <!-- ════════════════════════════════════════════════════════════════════
           SECTION 1: PRIMARY — Quick-Start Config (the main event)
           ════════════════════════════════════════════════════════════════════ -->

      <!-- Newly created key banner -->
      <Alert v-if="newlyCreatedKey" class="border-green-500/30 bg-green-500/5">
        <CircleCheck class="size-4 text-green-600 dark:text-green-400" />
        <AlertDescription class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <span class="font-medium text-green-700 dark:text-green-300">API key "{{ newlyCreatedKey.name }}" created.</span>
            <span class="text-muted-foreground"> Copy your config now — the secret won't be shown again.</span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <code class="rounded bg-muted px-2 py-1 font-mono text-xs truncate max-w-[180px]" :title="newlyCreatedKey.secret">
              {{ newlyCreatedKey.secret }}
            </code>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  :variant="secretCopied ? 'outline' : 'default'"
                  size="sm"
                  class="shrink-0 gap-1.5"
                  @click="copySecret"
                >
                  <component :is="secretCopied ? Check : Copy" class="size-3.5" />
                  {{ secretCopied ? 'Copied' : 'Copy Key' }}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Copy the raw API key secret</TooltipContent>
            </Tooltip>
          </div>
        </AlertDescription>
      </Alert>

      <!-- Connection Configuration Card — THE primary UI -->
      <Card class="border-primary/20">
        <CardHeader class="pb-4">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <Zap class="size-4 text-primary" />
              <CardTitle class="text-base">Quick Setup</CardTitle>
            </div>
            <Badge variant="secondary" class="gap-1.5 shrink-0">
              <div class="size-1.5 rounded-full" :class="configReady ? 'bg-green-500' : 'bg-yellow-500'" />
              {{ configReady ? 'Ready' : 'Needs API Key' }}
            </Badge>
          </div>
          <CardDescription>
            Create an API key, then copy the configuration for your MCP client.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- API Key status section -->
          <div class="space-y-3">
            <div class="flex items-center gap-2">
              <KeyRound class="size-3.5 text-muted-foreground" />
              <Label class="text-sm font-medium">API Key</Label>
            </div>

            <!-- Loading -->
            <div v-if="isLoading" class="flex items-center gap-2 py-2">
              <Loader2 class="size-3.5 animate-spin text-muted-foreground" />
              <span class="text-sm text-muted-foreground">Loading keys...</span>
            </div>

            <!-- State: Just created a key — show success with real secret in configs -->
            <template v-else-if="newlyCreatedKey">
              <div class="flex items-center gap-2 rounded-md border border-green-500/30 bg-green-500/5 px-3 py-2">
                <CircleCheck class="size-3.5 text-green-600 dark:text-green-400 shrink-0" />
                <span class="text-sm text-green-700 dark:text-green-300">
                  Using key "<span class="font-medium">{{ newlyCreatedKey.name }}</span>" — configs below contain the real secret.
                </span>
              </div>
            </template>

            <!-- State: Has existing keys but no fresh secret -->
            <template v-else-if="activeKeys.length > 0">
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p class="text-sm text-muted-foreground">
                  You have {{ activeKeys.length }} API key{{ activeKeys.length === 1 ? '' : 's' }}.
                  Create a new one to get a ready-to-paste config, or use an existing key's secret.
                </p>
                <Dialog v-model:open="createDialogOpen">
                  <DialogTrigger as-child>
                    <Button variant="default" size="sm" class="shrink-0 gap-1.5">
                      <Plus class="size-3.5" />
                      Create New Key
                    </Button>
                  </DialogTrigger>
                  <DialogContent class="sm:max-w-md">
                    <DialogHeader>
                      <DialogTitle>Create API Key</DialogTitle>
                      <DialogDescription>
                        Generate a new API key for MCP integration.
                      </DialogDescription>
                    </DialogHeader>
                    <form class="space-y-4" @submit.prevent="handleCreateKey">
                      <div class="space-y-2">
                        <Label for="mcp-key-name">Name <span class="text-destructive">*</span></Label>
                        <Input
                          id="mcp-key-name"
                          v-model="createForm.name"
                          placeholder="e.g. MCP - Claude Code"
                          :disabled="isCreating"
                        />
                      </div>
                      <div class="space-y-2">
                        <Label for="mcp-key-expiry">Expires in (days)</Label>
                        <Input
                          id="mcp-key-expiry"
                          v-model.number="createForm.expires_in_days"
                          type="number"
                          :min="1"
                          :max="3650"
                          :disabled="isCreating"
                        />
                        <p class="text-xs text-muted-foreground">Between 1 and 3650 days</p>
                        <p v-if="createExpiryError" class="text-sm text-destructive">{{ createExpiryError }}</p>
                      </div>
                      <DialogFooter>
                        <DialogClose as-child>
                          <Button type="button" variant="outline" :disabled="isCreating">Cancel</Button>
                        </DialogClose>
                        <Button type="submit" :disabled="isCreating || !createForm.name.trim()">
                          <Loader2 v-if="isCreating" class="animate-spin" />
                          {{ isCreating ? 'Creating...' : 'Create Key' }}
                        </Button>
                      </DialogFooter>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </template>

            <!-- State: No keys at all — prompt to create -->
            <template v-else>
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p class="text-sm text-muted-foreground">
                  No API keys found. Create one to generate connection configs.
                </p>
                <Dialog v-model:open="createDialogOpen">
                  <DialogTrigger as-child>
                    <Button variant="default" size="sm" class="shrink-0 gap-1.5">
                      <Plus class="size-3.5" />
                      Create API Key
                    </Button>
                  </DialogTrigger>
                  <DialogContent class="sm:max-w-md">
                    <DialogHeader>
                      <DialogTitle>Create API Key</DialogTitle>
                      <DialogDescription>
                        Generate a new API key for MCP integration.
                      </DialogDescription>
                    </DialogHeader>
                    <form class="space-y-4" @submit.prevent="handleCreateKey">
                      <div class="space-y-2">
                        <Label for="mcp-key-name-empty">Name <span class="text-destructive">*</span></Label>
                        <Input
                          id="mcp-key-name-empty"
                          v-model="createForm.name"
                          placeholder="e.g. MCP - Claude Code"
                          :disabled="isCreating"
                        />
                      </div>
                      <div class="space-y-2">
                        <Label for="mcp-key-expiry-empty">Expires in (days)</Label>
                        <Input
                          id="mcp-key-expiry-empty"
                          v-model.number="createForm.expires_in_days"
                          type="number"
                          :min="1"
                          :max="3650"
                          :disabled="isCreating"
                        />
                        <p class="text-xs text-muted-foreground">Between 1 and 3650 days</p>
                        <p v-if="createExpiryError" class="text-sm text-destructive">{{ createExpiryError }}</p>
                      </div>
                      <DialogFooter>
                        <DialogClose as-child>
                          <Button type="button" variant="outline" :disabled="isCreating">Cancel</Button>
                        </DialogClose>
                        <Button type="submit" :disabled="isCreating || !createForm.name.trim()">
                          <Loader2 v-if="isCreating" class="animate-spin" />
                          {{ isCreating ? 'Creating...' : 'Create Key' }}
                        </Button>
                      </DialogFooter>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </template>
          </div>

          <Separator />

          <!-- Config tabs -->
          <Tabs default-value="claude-code" class="w-full">
            <TabsList class="grid w-full grid-cols-4">
              <TabsTrigger value="claude-code" class="text-xs sm:text-sm">Claude Code</TabsTrigger>
              <TabsTrigger value="cursor" class="text-xs sm:text-sm">Cursor</TabsTrigger>
              <TabsTrigger value="claude-desktop" class="text-xs sm:text-sm">Claude Desktop</TabsTrigger>
              <TabsTrigger value="curl" class="text-xs sm:text-sm">cURL</TabsTrigger>
            </TabsList>

            <!-- Claude Code -->
            <TabsContent value="claude-code" class="mt-3 space-y-2">
              <p class="text-sm text-muted-foreground">
                Run this command in your terminal:
              </p>
              <div class="relative">
                <pre class="overflow-x-auto rounded-md border bg-muted/50 p-4 pr-14 font-mono text-[13px] leading-relaxed text-foreground whitespace-pre">{{ mcpConfigClaudeDisplay(configSecret) }}</pre>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="absolute right-2 top-2 size-8 text-muted-foreground hover:text-foreground"
                      :class="copiedConfigTab === 'Claude Code' ? 'text-green-600 dark:text-green-400' : ''"
                      @click="copyConfig('Claude Code', mcpConfigClaudeCopy(configSecret))"
                    >
                      <component :is="copiedConfigTab === 'Claude Code' ? Check : Copy" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ copiedConfigTab === 'Claude Code' ? 'Copied!' : 'Copy as single-line command' }}</TooltipContent>
                </Tooltip>
              </div>
            </TabsContent>

            <!-- Cursor -->
            <TabsContent value="cursor" class="mt-3 space-y-2">
              <p class="text-sm text-muted-foreground">
                Add to <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">.cursor/mcp.json</code>:
              </p>
              <div class="relative">
                <pre class="overflow-x-auto rounded-md border bg-muted/50 p-4 pr-14 font-mono text-[13px] leading-relaxed text-foreground whitespace-pre">{{ mcpConfigCursor(configSecret) }}</pre>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="absolute right-2 top-2 size-8 text-muted-foreground hover:text-foreground"
                      :class="copiedConfigTab === 'Cursor' ? 'text-green-600 dark:text-green-400' : ''"
                      @click="copyConfig('Cursor', mcpConfigCursor(configSecret))"
                    >
                      <component :is="copiedConfigTab === 'Cursor' ? Check : Copy" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ copiedConfigTab === 'Cursor' ? 'Copied!' : 'Copy config' }}</TooltipContent>
                </Tooltip>
              </div>
            </TabsContent>

            <!-- Claude Desktop -->
            <TabsContent value="claude-desktop" class="mt-3 space-y-2">
              <p class="text-sm text-muted-foreground">
                Add to <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">claude_desktop_config.json</code>:
              </p>
              <div class="relative">
                <pre class="overflow-x-auto rounded-md border bg-muted/50 p-4 pr-14 font-mono text-[13px] leading-relaxed text-foreground whitespace-pre">{{ mcpConfigDesktop(configSecret) }}</pre>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="absolute right-2 top-2 size-8 text-muted-foreground hover:text-foreground"
                      :class="copiedConfigTab === 'Claude Desktop' ? 'text-green-600 dark:text-green-400' : ''"
                      @click="copyConfig('Claude Desktop', mcpConfigDesktop(configSecret))"
                    >
                      <component :is="copiedConfigTab === 'Claude Desktop' ? Check : Copy" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ copiedConfigTab === 'Claude Desktop' ? 'Copied!' : 'Copy config' }}</TooltipContent>
                </Tooltip>
              </div>
            </TabsContent>

            <!-- cURL -->
            <TabsContent value="curl" class="mt-3 space-y-2">
              <p class="text-sm text-muted-foreground">
                Test your connection with a cURL request:
              </p>
              <div class="relative">
                <pre class="overflow-x-auto rounded-md border bg-muted/50 p-4 pr-14 font-mono text-[13px] leading-relaxed text-foreground whitespace-pre">{{ mcpConfigCurlDisplay(configSecret) }}</pre>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="absolute right-2 top-2 size-8 text-muted-foreground hover:text-foreground"
                      :class="copiedConfigTab === 'cURL' ? 'text-green-600 dark:text-green-400' : ''"
                      @click="copyConfig('cURL', mcpConfigCurlCopy(configSecret))"
                    >
                      <component :is="copiedConfigTab === 'cURL' ? Check : Copy" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ copiedConfigTab === 'cURL' ? 'Copied!' : 'Copy as single-line command' }}</TooltipContent>
                </Tooltip>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <!-- ════════════════════════════════════════════════════════════════════
           SECTION 2: SECONDARY — Collapsible Reference Sections
           ════════════════════════════════════════════════════════════════════ -->

      <!-- Endpoint Details (collapsible) -->
      <Card>
        <button
          class="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset rounded-lg"
          :aria-expanded="showDetails"
          aria-controls="endpoint-details-content"
          @click="showDetails = !showDetails"
        >
          <div class="flex items-center gap-2">
            <Info class="size-4 text-muted-foreground" />
            <span class="text-sm font-medium">Endpoint Details</span>
            <Badge variant="outline" class="text-[11px]">Reference</Badge>
          </div>
          <ChevronDown
            class="size-4 text-muted-foreground transition-transform duration-200"
            :class="showDetails ? '' : '-rotate-90'"
          />
        </button>

        <div
          v-if="showDetails"
          id="endpoint-details-content"
          role="region"
        >
          <Separator />
          <CardContent class="pt-4 space-y-4">
            <!-- URL -->
            <div class="space-y-1.5">
              <p class="text-xs font-medium text-muted-foreground uppercase tracking-wider">MCP Endpoint URL</p>
              <div class="flex items-center gap-2">
                <code class="flex-1 min-w-0 rounded-md border bg-muted/50 px-3 py-2 font-mono text-sm break-all">{{ mcpEndpointUrl }}</code>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="shrink-0 size-8 text-muted-foreground hover:text-foreground"
                      :class="endpointCopied ? 'text-green-600 dark:text-green-400' : ''"
                      @click="copyEndpoint"
                    >
                      <component :is="endpointCopied ? Check : Copy" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ endpointCopied ? 'Copied!' : 'Copy URL' }}</TooltipContent>
                </Tooltip>
              </div>
            </div>

            <!-- Metadata grid -->
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div class="rounded-md border bg-muted/30 p-3 space-y-1">
                <p class="text-xs font-medium text-muted-foreground">Transport</p>
                <Badge variant="default">Streamable HTTP</Badge>
              </div>
              <div class="rounded-md border bg-muted/30 p-3 space-y-1">
                <p class="text-xs font-medium text-muted-foreground">Authentication</p>
                <Badge variant="secondary">API Key + Tenant ID</Badge>
              </div>
            </div>

            <!-- Required Headers — now with actual values -->
            <div class="space-y-2">
              <p class="text-xs font-medium text-muted-foreground uppercase tracking-wider">Required Headers</p>
              <div class="space-y-2">
                <!-- X-API-Key header -->
                <div class="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
                  <code class="text-xs font-mono font-medium text-foreground shrink-0">X-API-Key:</code>
                  <code
                    class="flex-1 min-w-0 font-mono text-xs truncate"
                    :class="hasRealSecret ? 'text-green-700 dark:text-green-400' : 'text-muted-foreground italic'"
                    :title="configSecret"
                  >
                    {{ configSecret }}
                  </code>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="shrink-0 size-7 text-muted-foreground hover:text-foreground"
                        :class="copiedHeader === 'X-API-Key' ? 'text-green-600 dark:text-green-400' : ''"
                        @click="copyHeaderValue('X-API-Key', configSecret)"
                      >
                        <component :is="copiedHeader === 'X-API-Key' ? Check : Copy" class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>{{ copiedHeader === 'X-API-Key' ? 'Copied!' : hasRealSecret ? 'Copy API key secret' : 'Copy placeholder' }}</TooltipContent>
                  </Tooltip>
                </div>

                <!-- X-Tenant-ID header -->
                <div class="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
                  <code class="text-xs font-mono font-medium text-foreground shrink-0">X-Tenant-ID:</code>
                  <code
                    class="flex-1 min-w-0 font-mono text-xs truncate"
                    :class="currentTenantId ? 'text-foreground' : 'text-muted-foreground italic'"
                    :title="tenantId"
                  >
                    {{ tenantId }}
                  </code>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="shrink-0 size-7 text-muted-foreground hover:text-foreground"
                        :class="copiedHeader === 'X-Tenant-ID' ? 'text-green-600 dark:text-green-400' : ''"
                        @click="copyHeaderValue('X-Tenant-ID', tenantId)"
                      >
                        <component :is="copiedHeader === 'X-Tenant-ID' ? Check : Copy" class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>{{ copiedHeader === 'X-Tenant-ID' ? 'Copied!' : 'Copy tenant ID' }}</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </div>
          </CardContent>
        </div>
      </Card>

      <!-- Available Tools (collapsible) -->
      <Card>
        <button
          class="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset rounded-lg"
          :aria-expanded="showTools"
          aria-controls="tools-content"
          @click="showTools = !showTools"
        >
          <div class="flex items-center gap-2">
            <Terminal class="size-4 text-muted-foreground" />
            <span class="text-sm font-medium">Available MCP Tools</span>
            <Badge variant="outline" class="text-[11px]">1 tool</Badge>
          </div>
          <ChevronDown
            class="size-4 text-muted-foreground transition-transform duration-200"
            :class="showTools ? '' : '-rotate-90'"
          />
        </button>

        <div
          v-if="showTools"
          id="tools-content"
          role="region"
        >
          <Separator />
          <CardContent class="pt-4">
            <div class="rounded-md border p-4 space-y-3">
              <div class="flex items-center gap-2">
                <Terminal class="size-4 text-primary" />
                <code class="text-sm font-semibold">query_graph</code>
                <Badge variant="success" class="text-[10px] px-1.5 py-0">Active</Badge>
              </div>
              <p class="text-sm text-muted-foreground leading-relaxed">
                Execute Cypher queries against the knowledge graph. Returns results as JSON.
              </p>
              <div class="space-y-2">
                <p class="text-xs font-medium text-muted-foreground uppercase tracking-wider">Parameters</p>
                <div class="space-y-1.5">
                  <div class="flex items-center gap-2 text-sm">
                    <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">cypher</code>
                    <span class="text-muted-foreground">string</span>
                    <Badge variant="default" class="text-[10px] px-1.5 py-0">required</Badge>
                  </div>
                  <div class="flex items-center gap-2 text-sm">
                    <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">timeout_seconds</code>
                    <span class="text-muted-foreground">number</span>
                    <Badge variant="secondary" class="text-[10px] px-1.5 py-0">optional</Badge>
                  </div>
                  <div class="flex items-center gap-2 text-sm">
                    <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">max_rows</code>
                    <span class="text-muted-foreground">number</span>
                    <Badge variant="secondary" class="text-[10px] px-1.5 py-0">optional</Badge>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </div>
      </Card>
    </template>
  </div>
</template>
