<script setup lang="ts">
import {
  KeyRound,
  Plus,
  Copy,
  Check,
  Trash2,
  AlertTriangle,
  RefreshCw,
  Terminal,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { ref, reactive, computed, onMounted } from 'vue'
import type { APIKeyResponse, APIKeyCreatedResponse } from '~/types'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const { createApiKey, listApiKeys, revokeApiKey } = useIamApi()
const { currentTenantId } = useApiClient()
const { extractErrorMessage } = useErrorHandler()
const config = useRuntimeConfig()

// ── State ──────────────────────────────────────────────────────────────────

const apiKeys = ref<APIKeyResponse[]>([])
const isLoading = ref(false)
const loadError = ref<string | null>(null)

const createDialogOpen = ref(false)
const createForm = reactive({ name: '', expires_in_days: 30 })
const isCreating = ref(false)
const createExpiryError = ref('')

const newlyCreatedKey = ref<APIKeyCreatedResponse | null>(null)
const secretCopied = ref(false)

const revokeDialogOpen = ref(false)
const keyToRevoke = ref<APIKeyResponse | null>(null)
const isRevoking = ref(false)

const copiedConfigTab = ref<string | null>(null)

// ── Computed ───────────────────────────────────────────────────────────────

const apiBaseUrl = computed(() => config.public.apiBaseUrl as string)
const tenantId = computed(() => currentTenantId.value ?? '<your-tenant-id>')

const activeKeys = computed(() => apiKeys.value.filter((k) => !k.is_revoked))
const revokedKeys = computed(() => apiKeys.value.filter((k) => k.is_revoked))

function mcpConfigClaude(secret: string): string {
  return `claude mcp add kartograph-mcp --transport http ${apiBaseUrl.value}/query/mcp -H "X-API-Key: ${secret}" -H "X-Tenant-ID: ${tenantId.value}"`
}

function mcpConfigCursor(secret: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        kartograph: {
          url: `${apiBaseUrl.value}/query/mcp`,
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
          args: ['-y', 'mcp-remote', `${apiBaseUrl.value}/query/mcp`],
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

// ── Load keys ──────────────────────────────────────────────────────────────

async function loadKeys() {
  isLoading.value = true
  loadError.value = null
  try {
    apiKeys.value = await listApiKeys()
  } catch (err: unknown) {
    loadError.value = extractErrorMessage(err)
    toast.error('Failed to load API keys', { description: loadError.value })
  } finally {
    isLoading.value = false
  }
}

onMounted(loadKeys)

// ── Create ─────────────────────────────────────────────────────────────────

async function handleCreate() {
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
    copiedConfigTab.value = null
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

// ── Copy to clipboard ──────────────────────────────────────────────────────

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

async function copySecret() {
  if (!newlyCreatedKey.value) return
  const ok = await copyToClipboard(newlyCreatedKey.value.secret, 'API key secret')
  if (ok) secretCopied.value = true
}

async function copyConfig(tab: string, text: string) {
  const ok = await copyToClipboard(text, `${tab} config`)
  if (ok) {
    copiedConfigTab.value = tab
    setTimeout(() => {
      copiedConfigTab.value = null
    }, 2000)
  }
}

// ── Revoke ─────────────────────────────────────────────────────────────────

function confirmRevoke(key: APIKeyResponse) {
  keyToRevoke.value = key
  revokeDialogOpen.value = true
}

async function handleRevoke() {
  if (!keyToRevoke.value) return
  isRevoking.value = true
  try {
    await revokeApiKey(keyToRevoke.value.id)
    toast.success(`API key "${keyToRevoke.value.name}" revoked`)
    await loadKeys()
  } catch (err: unknown) {
    toast.error('Failed to revoke API key', {
      description: extractErrorMessage(err),
    })
  } finally {
    revokeDialogOpen.value = false
    keyToRevoke.value = null
    isRevoking.value = false
  }
}

// ── Dismiss newly created key ──────────────────────────────────────────────

function dismissCreatedKey() {
  newlyCreatedKey.value = null
  secretCopied.value = false
  copiedConfigTab.value = null
}

// ── Format helpers ─────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isExpired(key: APIKeyResponse): boolean {
  return new Date(key.expires_at) < new Date()
}

function keyStatus(key: APIKeyResponse): 'active' | 'revoked' | 'expired' {
  if (key.is_revoked) return 'revoked'
  if (isExpired(key)) return 'expired'
  return 'active'
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <KeyRound class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">API Keys</h1>
          <p class="text-sm text-muted-foreground">
            Create and manage API keys for programmatic access
          </p>
        </div>
      </div>

      <!-- Create API Key Dialog -->
      <Dialog v-model:open="createDialogOpen">
        <DialogTrigger as-child>
          <Button>
            <Plus class="mr-2 size-4" />
            Create API Key
          </Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
            <DialogDescription>
              Generate a new API key for programmatic access to Kartograph.
            </DialogDescription>
          </DialogHeader>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <div class="space-y-2">
              <Label for="key-name">Name <span class="text-destructive">*</span></Label>
              <Input
                id="key-name"
                v-model="createForm.name"
                placeholder="e.g. CI/CD Pipeline"
                :disabled="isCreating"
              />
            </div>
            <div class="space-y-2">
              <Label for="key-expiry">Expires in (days)</Label>
              <Input
                id="key-expiry"
                v-model.number="createForm.expires_in_days"
                type="number"
                :min="1"
                :max="3650"
                :disabled="isCreating"
              />
              <p class="text-xs text-muted-foreground">Between 1 and 3650 days (10 years)</p>
              <p v-if="createExpiryError" class="text-sm text-destructive">{{ createExpiryError }}</p>
            </div>
            <DialogFooter>
              <DialogClose as-child>
                <Button type="button" variant="outline" :disabled="isCreating">Cancel</Button>
              </DialogClose>
              <Button type="submit" :disabled="isCreating || !createForm.name.trim()">
                {{ isCreating ? 'Creating...' : 'Create Key' }}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <Separator />

    <!-- Newly Created Key Alert -->
    <div v-if="newlyCreatedKey" class="space-y-4">
      <Alert variant="warning">
        <AlertTriangle class="size-4" />
        <AlertTitle>
          Save your API key
        </AlertTitle>
        <AlertDescription>
          This is the only time the full key will be shown. Copy it now and store it securely.
        </AlertDescription>
      </Alert>

      <Card class="border-amber-500/30">
        <CardHeader>
          <CardTitle class="text-base">{{ newlyCreatedKey.name }}</CardTitle>
          <CardDescription>
            Prefix: <code class="font-mono text-xs">{{ newlyCreatedKey.prefix }}...</code>
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- Secret display -->
          <div class="space-y-2">
            <Label>API Key Secret</Label>
            <div class="flex items-center gap-2">
              <code
                class="flex-1 rounded-md border bg-muted px-3 py-2 font-mono text-sm break-all"
              >
                {{ newlyCreatedKey.secret }}
              </code>
              <Button variant="outline" size="icon" @click="copySecret">
                <component :is="secretCopied ? Check : Copy" class="size-4" />
              </Button>
            </div>
          </div>

          <Separator />

          <!-- MCP Configuration Generator -->
          <div class="space-y-3">
            <div class="flex items-center gap-2">
              <Terminal class="size-4 text-muted-foreground" />
              <h3 class="font-semibold">Connect to Kartograph</h3>
            </div>
            <p class="text-sm text-muted-foreground">
              Use these configurations to connect your tools to Kartograph via MCP.
            </p>

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
                  <pre
                    class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground"
                  >{{ mcpConfigClaude(newlyCreatedKey.secret) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('Claude Code', mcpConfigClaude(newlyCreatedKey!.secret))"
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
                  <pre
                    class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground"
                  >{{ mcpConfigCursor(newlyCreatedKey.secret) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('Cursor', mcpConfigCursor(newlyCreatedKey!.secret))"
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
                  <pre
                    class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground"
                  >{{ mcpConfigDesktop(newlyCreatedKey.secret) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('Claude Desktop', mcpConfigDesktop(newlyCreatedKey!.secret))"
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
                  <pre
                    class="overflow-x-auto rounded-md border bg-muted p-4 font-mono text-sm text-foreground"
                  >{{ mcpConfigCurl(newlyCreatedKey.secret) }}</pre>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    @click="copyConfig('cURL', mcpConfigCurl(newlyCreatedKey!.secret))"
                  >
                    <component :is="copiedConfigTab === 'cURL' ? Check : Copy" class="size-4" />
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </CardContent>
        <div class="flex justify-end border-t px-6 py-4">
          <Button variant="outline" @click="dismissCreatedKey">Done</Button>
        </div>
      </Card>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <RefreshCw class="size-6 animate-spin text-muted-foreground" />
      <span class="ml-2 text-muted-foreground">Loading API keys...</span>
    </div>

    <!-- Error state -->
    <Alert v-else-if="loadError" variant="destructive">
      <AlertTriangle class="size-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {{ loadError }}
        <Button variant="link" class="ml-2 h-auto p-0" @click="loadKeys">Retry</Button>
      </AlertDescription>
    </Alert>

    <!-- Key list -->
    <template v-else>
      <!-- Active Keys -->
      <Card v-if="activeKeys.length > 0">
        <CardHeader>
          <CardTitle class="text-base">Active Keys</CardTitle>
          <CardDescription>
            {{ activeKeys.length }} active {{ activeKeys.length === 1 ? 'key' : 'keys' }}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead>Status</TableHead>
                <TableHead class="w-[50px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="key in activeKeys" :key="key.id">
                <TableCell class="font-medium">{{ key.name }}</TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                    {{ key.prefix }}...
                  </code>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ formatDate(key.created_at) }}
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ formatDate(key.expires_at) }}
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ key.last_used_at ? formatDateTime(key.last_used_at) : 'Never' }}
                </TableCell>
                <TableCell>
                  <Badge
                    :variant="keyStatus(key) === 'active' ? 'success' : keyStatus(key) === 'expired' ? 'destructive' : 'secondary'"
                  >
                    {{ keyStatus(key) }}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="text-destructive hover:bg-destructive/10 hover:text-destructive"
                    :aria-label="`Revoke API key ${key.name}`"
                    @click="confirmRevoke(key)"
                  >
                    <Trash2 class="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <!-- Revoked Keys -->
      <Card v-if="revokedKeys.length > 0">
        <CardHeader>
          <CardTitle class="text-base text-muted-foreground">Revoked Keys</CardTitle>
          <CardDescription>
            {{ revokedKeys.length }} revoked {{ revokedKeys.length === 1 ? 'key' : 'keys' }}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="key in revokedKeys" :key="key.id" class="opacity-60">
                <TableCell class="font-medium">{{ key.name }}</TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                    {{ key.prefix }}...
                  </code>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ formatDate(key.created_at) }}
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ formatDate(key.expires_at) }}
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ key.last_used_at ? formatDateTime(key.last_used_at) : 'Never' }}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">revoked</Badge>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <!-- Empty state -->
      <div
        v-if="!isLoading && apiKeys.length === 0 && !newlyCreatedKey"
        class="py-12 text-center"
      >
        <KeyRound class="mx-auto size-12 text-muted-foreground/50" />
        <h3 class="mt-4 text-lg font-semibold">No API keys yet</h3>
        <p class="mt-1 text-sm text-muted-foreground">
          Create your first API key to get started with programmatic access.
        </p>
      </div>
    </template>

    <!-- Revoke Confirmation Dialog -->
    <Dialog v-model:open="revokeDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Revoke API Key</DialogTitle>
          <DialogDescription>
            Are you sure you want to revoke
            <span class="font-semibold">{{ keyToRevoke?.name }}</span>
            (<code class="font-mono text-xs">{{ keyToRevoke?.prefix }}...</code>)?
            Any applications using this key will immediately lose access.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline" :disabled="isRevoking">Cancel</Button>
          </DialogClose>
          <Button variant="destructive" :disabled="isRevoking" @click="handleRevoke">
            {{ isRevoking ? 'Revoking...' : 'Revoke Key' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
