<script setup lang="ts">
import {
  KeyRound,
  Plus,
  Copy,
  Check,
  Trash2,
  AlertTriangle,
  RefreshCw,
  Building2,
  Plug,
  ShieldAlert,
  Clock,
  Loader2,
  Eye,
  EyeOff,
  Info,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { UserIdDisplay } from '@/components/ui/user-id'

const { createApiKey, listApiKeys, revokeApiKey } = useIamApi()
const { currentTenantId } = useApiClient()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()
const transientSecret = useTransientSecret()

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
const secretVisible = ref(true)

const revokeDialogOpen = ref(false)
const keyToRevoke = ref<APIKeyResponse | null>(null)
const isRevoking = ref(false)

const copiedPrefix = ref<string | null>(null)

// ── Computed ───────────────────────────────────────────────────────────────

const activeKeys = computed(() =>
  apiKeys.value.filter((k) => !k.is_revoked && !isExpired(k)),
)
const expiredKeys = computed(() =>
  apiKeys.value.filter((k) => !k.is_revoked && isExpired(k)),
)
const revokedKeys = computed(() => apiKeys.value.filter((k) => k.is_revoked))

const totalKeys = computed(() => apiKeys.value.length)

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

onMounted(() => {
  if (hasTenant.value) loadKeys()
})

// Re-fetch when tenant changes
watch(tenantVersion, () => {
  if (hasTenant.value) {
    newlyCreatedKey.value = null
    secretCopied.value = false
    loadKeys()
  }
})

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
    secretVisible.value = true
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

async function copyKeyPrefix(prefix: string) {
  const ok = await copyToClipboard(prefix, 'Key prefix')
  if (ok) {
    copiedPrefix.value = prefix
    setTimeout(() => {
      copiedPrefix.value = null
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
  secretVisible.value = true
}

// ── Navigate to MCP with secret ────────────────────────────────────────────

// Guard flag: when true, onUnmounted should NOT clear the transient secret
// because we intentionally set it for the MCP page to consume.
const navigatingToMcp = ref(false)

function navigateToMcpWithSecret() {
  if (newlyCreatedKey.value) {
    transientSecret.set(newlyCreatedKey.value.secret, newlyCreatedKey.value.name)
  }
  navigatingToMcp.value = true
  navigateTo('/integrate/mcp')
}

// Clear transient secret if user navigates away without going to MCP page.
// Skip the clear when we're intentionally navigating to MCP — in Nuxt SPA
// mode, onUnmounted fires before the target page's onMounted, so clearing
// here would race with the MCP page's consume() call.
onUnmounted(() => {
  if (!navigatingToMcp.value) {
    transientSecret.clear()
  }
})

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

function daysUntilExpiry(key: APIKeyResponse): number {
  const now = new Date()
  const expiry = new Date(key.expires_at)
  return Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

function maskedSecret(secret: string): string {
  if (secret.length <= 8) return secret
  return secret.slice(0, 8) + '\u2022'.repeat(Math.min(24, secret.length - 8))
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="rounded-lg bg-primary/10 p-2">
          <KeyRound class="size-5 text-primary" />
        </div>
        <div>
          <h1 class="text-2xl font-bold tracking-tight">API Keys</h1>
          <p class="text-sm text-muted-foreground">
            Create, view, and manage API keys for authenticating with Kartograph.
          </p>
        </div>
      </div>

      <!-- Create API Key Dialog -->
      <Dialog v-model:open="createDialogOpen">
        <DialogTrigger as-child>
          <Button :disabled="!hasTenant">
            <Plus class="mr-2 size-4" />
            Create API Key
          </Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
            <DialogDescription>
              Generate a new API key for programmatic access to Kartograph. Use descriptive names
              to help identify keys later.
            </DialogDescription>
          </DialogHeader>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <div class="space-y-2">
              <Label for="key-name">Name <span class="text-destructive">*</span></Label>
              <Input
                id="key-name"
                v-model="createForm.name"
                placeholder="e.g. CI/CD Pipeline, MCP - Claude Code"
                :disabled="isCreating"
              />
              <p class="text-xs text-muted-foreground">
                Choose a name that describes how or where this key is used.
              </p>
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
                <Loader2 v-if="isCreating" class="mr-2 size-4 animate-spin" />
                {{ isCreating ? 'Creating...' : 'Create Key' }}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view API keys.</p>
    </div>

    <template v-else>

    <!-- Newly Created Key Banner -->
    <Card v-if="newlyCreatedKey" class="border-amber-500/30 bg-amber-500/5">
      <CardContent class="pt-6 space-y-4">
        <!-- Warning header -->
        <div class="flex items-start gap-3">
          <div class="rounded-full bg-amber-500/10 p-2 shrink-0">
            <ShieldAlert class="size-4 text-amber-600 dark:text-amber-400" />
          </div>
          <div class="min-w-0 flex-1">
            <h3 class="font-semibold text-amber-700 dark:text-amber-300">
              Save your API key secret
            </h3>
            <p class="text-sm text-amber-600/80 dark:text-amber-400/80 mt-0.5">
              This is the only time the full secret will be shown. Copy it now and store it securely.
              You will not be able to retrieve it again.
            </p>
          </div>
        </div>

        <!-- Key details -->
        <div class="space-y-3 rounded-md border border-amber-500/20 bg-background p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium">{{ newlyCreatedKey.name }}</span>
              <Badge variant="success">active</Badge>
            </div>
            <code class="text-xs text-muted-foreground font-mono">{{ newlyCreatedKey.prefix }}...</code>
          </div>

          <Separator />

          <!-- Secret display -->
          <div class="space-y-1.5">
            <div class="flex items-center gap-2">
              <Label class="text-xs text-muted-foreground uppercase tracking-wider">API Key Secret</Label>
            </div>
            <div class="flex items-center gap-2">
              <code
                class="flex-1 min-w-0 rounded-md border bg-muted px-3 py-2.5 font-mono text-sm break-all select-all"
              >
                {{ secretVisible ? newlyCreatedKey.secret : maskedSecret(newlyCreatedKey.secret) }}
              </code>
              <div class="flex items-center gap-1 shrink-0">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="outline"
                      size="icon"
                      class="size-9"
                      @click="secretVisible = !secretVisible"
                    >
                      <component :is="secretVisible ? EyeOff : Eye" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ secretVisible ? 'Hide secret' : 'Show secret' }}</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      :variant="secretCopied ? 'outline' : 'default'"
                      size="icon"
                      class="size-9"
                      @click="copySecret"
                    >
                      <component :is="secretCopied ? Check : Copy" class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ secretCopied ? 'Copied!' : 'Copy secret' }}</TooltipContent>
                </Tooltip>
              </div>
            </div>
          </div>
        </div>

        <!-- MCP cross-link -->
        <div class="flex items-center justify-between gap-4 rounded-md border bg-muted/50 px-4 py-3">
          <div class="flex items-center gap-2 min-w-0">
            <Plug class="size-4 text-muted-foreground shrink-0" />
            <p class="text-sm text-muted-foreground">
              Need to configure an MCP client? Use the integration page for copy-paste configs.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            class="shrink-0"
            @click="navigateToMcpWithSecret"
          >
            MCP Integration
          </Button>
        </div>

        <!-- Dismiss -->
        <div class="flex justify-end">
          <Button variant="ghost" size="sm" @click="dismissCreatedKey">
            Dismiss
          </Button>
        </div>
      </CardContent>
    </Card>

    <!-- Loading state -->
    <div v-if="isLoading && !newlyCreatedKey" class="flex items-center justify-center py-12">
      <Loader2 class="size-5 animate-spin text-muted-foreground" />
      <span class="ml-2 text-sm text-muted-foreground">Loading API keys...</span>
    </div>

    <!-- Error state -->
    <Alert v-else-if="loadError" variant="destructive">
      <AlertTriangle class="size-4" />
      <AlertTitle>Failed to load API keys</AlertTitle>
      <AlertDescription class="flex items-center gap-2">
        {{ loadError }}
        <Button variant="outline" size="sm" class="ml-2" @click="loadKeys">
          <RefreshCw class="mr-1.5 size-3.5" />
          Retry
        </Button>
      </AlertDescription>
    </Alert>

    <!-- Key list -->
    <template v-else>
      <!-- Summary bar -->
      <div
        v-if="totalKeys > 0"
        class="flex items-center gap-4 text-sm text-muted-foreground"
      >
        <span>{{ totalKeys }} total {{ totalKeys === 1 ? 'key' : 'keys' }}</span>
        <Separator orientation="vertical" class="h-4" />
        <div class="flex items-center gap-3">
          <span v-if="activeKeys.length > 0" class="flex items-center gap-1.5">
            <span class="size-2 rounded-full bg-green-500" />
            {{ activeKeys.length }} active
          </span>
          <span v-if="expiredKeys.length > 0" class="flex items-center gap-1.5">
            <span class="size-2 rounded-full bg-amber-500" />
            {{ expiredKeys.length }} expired
          </span>
          <span v-if="revokedKeys.length > 0" class="flex items-center gap-1.5">
            <span class="size-2 rounded-full bg-muted-foreground/50" />
            {{ revokedKeys.length }} revoked
          </span>
        </div>
      </div>

      <!-- Active Keys -->
      <Card v-if="activeKeys.length > 0">
        <CardHeader class="pb-3">
          <div class="flex items-center gap-2">
            <span class="size-2 rounded-full bg-green-500" />
            <CardTitle class="text-base">Active Keys</CardTitle>
            <Badge variant="secondary" class="ml-1">{{ activeKeys.length }}</Badge>
          </div>
        </CardHeader>
        <CardContent class="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created By</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead class="w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="key in activeKeys" :key="key.id">
                <TableCell class="font-medium">{{ key.name }}</TableCell>
                <TableCell>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <button
                        class="inline-flex items-center gap-1.5 rounded bg-muted px-1.5 py-0.5 font-mono text-xs transition-colors hover:bg-muted/80"
                        @click="copyKeyPrefix(key.prefix)"
                      >
                        {{ key.prefix }}...
                        <component
                          :is="copiedPrefix === key.prefix ? Check : Copy"
                          class="size-3"
                          :class="copiedPrefix === key.prefix ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'"
                        />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>{{ copiedPrefix === key.prefix ? 'Copied!' : 'Copy prefix' }}</TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <UserIdDisplay :user-id="key.created_by_user_id" />
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ formatDate(key.created_at) }}
                </TableCell>
                <TableCell>
                  <span
                    class="text-sm"
                    :class="daysUntilExpiry(key) <= 30
                      ? 'text-amber-600 dark:text-amber-400 font-medium'
                      : 'text-muted-foreground'"
                  >
                    {{ formatDate(key.expires_at) }}
                    <span v-if="daysUntilExpiry(key) <= 30" class="text-xs ml-1">
                      ({{ daysUntilExpiry(key) }}d)
                    </span>
                  </span>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ key.last_used_at ? formatDateTime(key.last_used_at) : 'Never' }}
                </TableCell>
                <TableCell>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                        @click="confirmRevoke(key)"
                      >
                        <Trash2 class="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Revoke key</TooltipContent>
                  </Tooltip>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <!-- Expired Keys (non-revoked but past expiry) -->
      <Card v-if="expiredKeys.length > 0">
        <CardHeader class="pb-3">
          <div class="flex items-center gap-2">
            <span class="size-2 rounded-full bg-amber-500" />
            <CardTitle class="text-base text-muted-foreground">Expired Keys</CardTitle>
            <Badge variant="secondary" class="ml-1">{{ expiredKeys.length }}</Badge>
          </div>
          <CardDescription>
            These keys have passed their expiration date and can no longer authenticate requests.
          </CardDescription>
        </CardHeader>
        <CardContent class="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created By</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Expired</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead class="w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="key in expiredKeys" :key="key.id" class="opacity-70">
                <TableCell class="font-medium">{{ key.name }}</TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                    {{ key.prefix }}...
                  </code>
                </TableCell>
                <TableCell>
                  <UserIdDisplay :user-id="key.created_by_user_id" />
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ formatDate(key.created_at) }}
                </TableCell>
                <TableCell>
                  <span class="text-sm text-amber-600 dark:text-amber-400">
                    {{ formatDate(key.expires_at) }}
                  </span>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ key.last_used_at ? formatDateTime(key.last_used_at) : 'Never' }}
                </TableCell>
                <TableCell>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                        @click="confirmRevoke(key)"
                      >
                        <Trash2 class="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Revoke key</TooltipContent>
                  </Tooltip>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <!-- Revoked Keys -->
      <Card v-if="revokedKeys.length > 0">
        <CardHeader class="pb-3">
          <div class="flex items-center gap-2">
            <span class="size-2 rounded-full bg-muted-foreground/50" />
            <CardTitle class="text-base text-muted-foreground">Revoked Keys</CardTitle>
            <Badge variant="secondary" class="ml-1">{{ revokedKeys.length }}</Badge>
          </div>
        </CardHeader>
        <CardContent class="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created By</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Expired</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="key in revokedKeys" :key="key.id" class="opacity-50">
                <TableCell class="font-medium line-through">{{ key.name }}</TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                    {{ key.prefix }}...
                  </code>
                </TableCell>
                <TableCell>
                  <UserIdDisplay :user-id="key.created_by_user_id" />
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
        class="py-16 text-center"
      >
        <div class="mx-auto rounded-full bg-muted p-4 w-fit">
          <KeyRound class="size-8 text-muted-foreground" />
        </div>
        <h3 class="mt-4 text-lg font-semibold">No API keys</h3>
        <p class="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
          API keys authenticate programmatic access to Kartograph, including MCP clients like Claude Code and Cursor.
        </p>
        <div class="flex items-center justify-center gap-3 mt-6">
          <Button @click="createDialogOpen = true">
            <Plus class="mr-2 size-4" />
            Create API Key
          </Button>
          <NuxtLink to="/integrate/mcp">
            <Button variant="outline">
              <Plug class="mr-2 size-4" />
              MCP Integration
            </Button>
          </NuxtLink>
        </div>
      </div>

      <!-- Info note about secrets -->
      <div
        v-if="!isLoading && apiKeys.length > 0"
        class="flex items-start gap-2.5 rounded-md border bg-muted/30 px-4 py-3"
      >
        <Info class="size-4 text-muted-foreground shrink-0 mt-0.5" />
        <div class="text-sm text-muted-foreground space-y-1">
          <p>
            API key secrets are only shown once at creation time.
            If you need a new secret, create a new key and revoke the old one.
          </p>
          <p>
            Setting up an MCP client?
            <NuxtLink to="/integrate/mcp" class="text-primary hover:underline underline-offset-4">
              Use the MCP Integration page
            </NuxtLink>
            for copy-paste configurations.
          </p>
        </div>
      </div>
    </template>

    </template>

    <!-- Revoke Confirmation Dialog -->
    <Dialog v-model:open="revokeDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <AlertTriangle class="size-5 text-destructive" />
            Revoke API Key
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to revoke
            <span class="font-semibold">{{ keyToRevoke?.name }}</span>
            (<code class="font-mono text-xs">{{ keyToRevoke?.prefix }}...</code>)?
            This action is immediate and cannot be undone. Any applications using this key will lose access.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline" :disabled="isRevoking">Cancel</Button>
          </DialogClose>
          <Button variant="destructive" :disabled="isRevoking" @click="handleRevoke">
            <Loader2 v-if="isRevoking" class="mr-2 size-4 animate-spin" />
            {{ isRevoking ? 'Revoking...' : 'Revoke Key' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
