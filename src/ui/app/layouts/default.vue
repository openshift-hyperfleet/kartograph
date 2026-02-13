<script setup lang="ts">
import { computed, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Building2,
  FolderTree,
  Users,
  KeyRound,
  Database,
  Share2,
  FileCode,
  Terminal,
  PanelLeftClose,
  PanelLeft,
  Menu,
  Moon,
  Sun,
  LogOut,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  Check,
  Hexagon,
  AlertTriangle,
  Loader2,
  LayoutDashboard,
  Plug,
  Cable,
  Settings2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useSidebar } from '@/composables/useSidebar'
import { useColorMode } from '@/composables/useColorMode'

const route = useRoute()
const { isCollapsed, isMobileOpen, toggleCollapsed, closeMobile } = useSidebar()
const { isDark, toggle: toggleColorMode } = useColorMode()

// ── Auth & Tenant state ────────────────────────────────────────────────────
const { user, isAuthenticated, logout } = useAuth()
const { listTenants } = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const {
  currentTenantId,
  tenants,
  tenantsLoading,
  tenantsLoaded,
  hasTenant,
  switchTenant,
  reconcileAfterFetch,
} = useTenant()

const displayName = computed(() => {
  if (!user.value) return 'User'
  const profile = user.value.profile
  return profile?.name ?? profile?.preferred_username ?? profile?.email ?? 'User'
})

const displayEmail = computed(() => {
  if (!user.value) return ''
  return user.value.profile?.email ?? ''
})

const avatarInitials = computed(() => {
  const name = displayName.value
  const parts = name.split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.substring(0, 2).toUpperCase()
})

// True when the user has exactly one tenant (show static display instead of dropdown)
const isSingleTenant = computed(() => tenants.value.length === 1)

// True when the user has multiple tenants
const isMultiTenant = computed(() => tenants.value.length > 1)

// The display name for the currently-selected tenant
const selectedTenantName = computed(() => {
  if (!currentTenantId.value) return null
  return tenants.value.find((t) => t.id === currentTenantId.value)?.name ?? null
})

// Accessible label for the tenant context
const tenantAriaLabel = computed(() => {
  if (tenantsLoading.value) return 'Loading tenants'
  if (tenantsLoaded.value && tenants.value.length === 0) return 'No tenants available. Navigate to create one.'
  if (selectedTenantName.value) return `Current tenant: ${selectedTenantName.value}. ${isMultiTenant.value ? 'Click to switch tenants.' : ''}`
  return 'Tenant selector'
})

function handleTenantChange(id: string) {
  const tenant = tenants.value.find((t) => t.id === id)
  switchTenant(id, tenant?.name)
}

async function fetchTenants() {
  tenantsLoading.value = true
  try {
    const fetched = await listTenants()
    reconcileAfterFetch(fetched)
  } catch (err) {
    toast.error('Failed to load tenants', {
      description: extractErrorMessage(err),
    })
  } finally {
    tenantsLoading.value = false
  }
}

async function handleLogout() {
  try {
    await logout()
  } catch (err) {
    toast.error('Logout failed')
  }
}

watch(isAuthenticated, (authenticated) => {
  if (authenticated) {
    fetchTenants()
  }
}, { immediate: true })

// ── Navigation (Token 2 + Token 6) ────────────────────────────────────────

interface NavItem {
  label: string
  icon: typeof Building2
  to: string
  disabled?: boolean
  badge?: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

const homeItem: NavItem = { label: 'Home', icon: LayoutDashboard, to: '/' }

const navSections: NavSection[] = [
  {
    title: 'Knowledge',
    items: [
      { label: 'Schema Browser', icon: Database, to: '/graph/schema' },
      { label: 'Explorer', icon: Share2, to: '/graph/explorer' },
      { label: 'Query Console', icon: Terminal, to: '/query' },
      { label: 'Mutations', icon: FileCode, to: '/graph/mutations' },
    ],
  },
  {
    title: 'Connect',
    items: [
      { label: 'Data Sources', icon: Cable, to: '#', disabled: true, badge: 'Soon' },
    ],
  },
  {
    title: 'Integrate',
    items: [
      { label: 'API Keys', icon: KeyRound, to: '/api-keys' },
      { label: 'MCP Endpoints', icon: Plug, to: '/integrate/mcp' },
    ],
  },
  {
    title: 'Settings',
    items: [
      { label: 'Workspaces', icon: FolderTree, to: '/workspaces' },
      { label: 'Groups', icon: Users, to: '/groups' },
    ],
  },
]

function isActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  if (to === '#') return false
  return route.path === to || route.path.startsWith(to + '/')
}

// ── Breadcrumbs (Token 4) ──────────────────────────────────────────────────

const breadcrumbs = computed(() => {
  const path = route.path
  const crumbs: Array<{ label: string; to?: string }> = [{ label: 'Home', to: '/' }]

  const routeLabels: Record<string, string> = {
    '/tenants': 'Tenants',
    '/workspaces': 'Workspaces',
    '/groups': 'Groups',
    '/api-keys': 'API Keys',
    '/graph/schema': 'Schema Browser',
    '/graph/explorer': 'Explorer',
    '/graph/mutations': 'Mutations',
    '/query': 'Query Console',
    '/integrate/mcp': 'MCP Integration',
  }

  if (path !== '/' && routeLabels[path]) {
    crumbs.push({ label: routeLabels[path] })
  }

  return crumbs
})

const sidebarWidth = computed(() => (isCollapsed.value ? 'w-16' : 'w-64'))
</script>

<template>
  <TooltipProvider :delay-duration="0">
    <div class="flex h-screen overflow-hidden bg-background">
      <!-- Desktop Sidebar -->
      <aside
        :class="[
          sidebarWidth,
          'hidden md:flex flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200 ease-in-out',
        ]"
      >
        <!-- Logo -->
        <div class="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
          <Hexagon class="size-6 shrink-0 text-sidebar-primary" />
          <span
            v-if="!isCollapsed"
            class="text-base font-semibold tracking-tight text-sidebar-foreground truncate"
          >
            Kartograph
          </span>
        </div>

        <!-- Tenant Selector (Desktop Sidebar) -->
        <div
          class="border-b border-sidebar-border px-2 py-2"
          role="region"
          :aria-label="tenantAriaLabel"
        >
          <!-- Loading state -->
          <div
            v-if="tenantsLoading"
            class="flex items-center gap-2 rounded-md px-2 py-2"
            :class="isCollapsed ? 'justify-center' : ''"
            role="status"
            aria-live="polite"
          >
            <Tooltip v-if="isCollapsed">
              <TooltipTrigger as-child>
                <div class="flex items-center justify-center">
                  <Loader2 class="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden="true" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" :side-offset="8">
                Loading tenants...
              </TooltipContent>
            </Tooltip>
            <template v-else>
              <Loader2 class="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden="true" />
              <span class="text-sm text-muted-foreground truncate">Loading...</span>
            </template>
          </div>

          <!-- Zero tenants -->
          <NuxtLink
            v-else-if="tenantsLoaded && tenants.length === 0"
            to="/tenants"
            class="group flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-2 transition-colors hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/50 dark:hover:bg-amber-950"
            :class="isCollapsed ? 'justify-center' : ''"
            role="link"
            :aria-label="tenantAriaLabel"
          >
            <Tooltip v-if="isCollapsed">
              <TooltipTrigger as-child>
                <div class="flex items-center justify-center">
                  <AlertTriangle class="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" :side-offset="8">
                No tenants — create one
              </TooltipContent>
            </Tooltip>
            <template v-else>
              <AlertTriangle class="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
              <span class="text-sm font-medium text-amber-700 dark:text-amber-300 truncate">No tenants</span>
            </template>
          </NuxtLink>

          <!-- Single tenant (static display with visual container) -->
          <div
            v-else-if="isSingleTenant"
            class="flex items-center gap-2 rounded-md bg-sidebar-accent px-2 py-2"
            :class="isCollapsed ? 'justify-center' : ''"
            role="status"
            :aria-label="tenantAriaLabel"
          >
            <Tooltip v-if="isCollapsed">
              <TooltipTrigger as-child>
                <div class="flex items-center justify-center">
                  <Building2 class="size-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" :side-offset="8">
                {{ selectedTenantName }}
              </TooltipContent>
            </Tooltip>
            <template v-else>
              <Building2 class="size-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
              <span class="text-sm font-medium text-sidebar-foreground truncate">{{ selectedTenantName }}</span>
            </template>
          </div>

          <!-- Multiple tenants: DropdownMenu-based picker (Token 5: "Manage Tenants" link) -->
          <DropdownMenu v-else>
            <Tooltip v-if="isCollapsed">
              <TooltipTrigger as-child>
                <DropdownMenuTrigger as-child>
                  <button
                    class="flex w-full items-center justify-center rounded-md bg-sidebar-accent p-2 transition-colors hover:bg-sidebar-accent/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                    :aria-label="tenantAriaLabel"
                  >
                    <Building2 class="size-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
                  </button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent side="right" :side-offset="8">
                {{ selectedTenantName ?? 'Select tenant' }}
              </TooltipContent>
            </Tooltip>
            <DropdownMenuTrigger v-else as-child>
              <button
                class="flex w-full items-center gap-2 rounded-md bg-sidebar-accent px-2 py-2 text-left transition-colors hover:bg-sidebar-accent/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                :aria-label="tenantAriaLabel"
              >
                <Building2 class="size-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
                <span class="flex-1 truncate text-sm font-medium text-sidebar-foreground">
                  {{ selectedTenantName ?? 'Select tenant...' }}
                </span>
                <ChevronsUpDown class="size-4 shrink-0 text-sidebar-foreground/50" aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              class="w-56"
              :side="isCollapsed ? 'right' : 'bottom'"
              :align="isCollapsed ? 'start' : 'start'"
              :side-offset="isCollapsed ? 8 : 4"
            >
              <DropdownMenuLabel class="text-xs text-muted-foreground">
                Switch tenant
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                v-for="tenant in tenants"
                :key="tenant.id"
                class="flex items-center gap-2"
                @click="handleTenantChange(tenant.id)"
              >
                <Building2 class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span class="flex-1 truncate">{{ tenant.name }}</span>
                <Check
                  v-if="tenant.id === currentTenantId"
                  class="size-4 shrink-0 text-sidebar-primary"
                  aria-hidden="true"
                />
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem as-child>
                <NuxtLink to="/tenants" class="flex items-center gap-2">
                  <Settings2 class="size-4 shrink-0 text-muted-foreground" />
                  <span>Manage Tenants</span>
                </NuxtLink>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 overflow-y-auto py-3" aria-label="Main navigation">
          <!-- Home item (standalone, above sections) -->
          <div class="mb-3 px-2">
            <div class="space-y-0.5">
              <template v-if="isCollapsed">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <NuxtLink
                      :to="homeItem.to"
                      :class="[
                        'flex items-center justify-center rounded-md p-2 transition-colors',
                        isActive(homeItem.to)
                          ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                          : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                      ]"
                    >
                      <component :is="homeItem.icon" class="size-4" />
                    </NuxtLink>
                  </TooltipTrigger>
                  <TooltipContent side="right" :side-offset="8">
                    {{ homeItem.label }}
                  </TooltipContent>
                </Tooltip>
              </template>

              <NuxtLink
                v-else
                :to="homeItem.to"
                :class="[
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive(homeItem.to)
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                ]"
              >
                <component :is="homeItem.icon" class="size-4 shrink-0" />
                <span class="truncate">{{ homeItem.label }}</span>
              </NuxtLink>
            </div>
          </div>

          <!-- Nav sections -->
          <div v-for="section in navSections" :key="section.title" class="mb-3">
            <div
              v-if="!isCollapsed"
              class="mb-1 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              {{ section.title }}
            </div>
            <Separator v-else class="mx-auto mb-2 w-8" />

            <div class="space-y-0.5 px-2">
              <template v-for="item in section.items" :key="item.to + item.label">
                <!-- Collapsed sidebar -->
                <template v-if="isCollapsed">
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <!-- Disabled item (collapsed) -->
                      <div
                        v-if="item.disabled"
                        class="flex items-center justify-center rounded-md p-2 opacity-50 cursor-not-allowed text-sidebar-foreground/70"
                      >
                        <component :is="item.icon" class="size-4" />
                      </div>
                      <!-- Normal item (collapsed) -->
                      <NuxtLink
                        v-else
                        :to="item.to"
                        :class="[
                          'flex items-center justify-center rounded-md p-2 transition-colors',
                          isActive(item.to)
                            ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                            : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                        ]"
                      >
                        <component :is="item.icon" class="size-4" />
                      </NuxtLink>
                    </TooltipTrigger>
                    <TooltipContent side="right" :side-offset="8">
                      {{ item.label }}{{ item.disabled ? ' (Coming Soon)' : '' }}
                    </TooltipContent>
                  </Tooltip>
                </template>

                <!-- Expanded sidebar -->
                <template v-else>
                  <!-- Disabled item (expanded) -->
                  <div
                    v-if="item.disabled"
                    class="flex items-center gap-3 rounded-md px-3 py-2 text-sm opacity-50 cursor-not-allowed text-sidebar-foreground/70"
                  >
                    <component :is="item.icon" class="size-4 shrink-0" />
                    <span class="truncate">{{ item.label }}</span>
                    <Badge v-if="item.badge" variant="secondary" class="ml-auto text-[10px] px-1.5 py-0">
                      {{ item.badge }}
                    </Badge>
                  </div>
                  <!-- Normal item (expanded) -->
                  <NuxtLink
                    v-else
                    :to="item.to"
                    :class="[
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                      isActive(item.to)
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                        : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                    ]"
                  >
                    <component :is="item.icon" class="size-4 shrink-0" />
                    <span class="truncate">{{ item.label }}</span>
                  </NuxtLink>
                </template>
              </template>
            </div>
          </div>
        </nav>

        <!-- Sidebar Footer -->
        <div class="border-t border-sidebar-border p-2">
          <Button
            variant="ghost"
            :size="isCollapsed ? 'icon' : 'sm'"
            :class="isCollapsed ? 'w-full' : 'w-full justify-start gap-2'"
            @click="toggleCollapsed"
          >
            <PanelLeftClose v-if="!isCollapsed" class="size-4 shrink-0" />
            <PanelLeft v-else class="size-4" />
            <span v-if="!isCollapsed" class="text-xs">Collapse</span>
          </Button>
        </div>
      </aside>

      <!-- Mobile Sidebar (Sheet) -->
      <Sheet v-model:open="isMobileOpen">
        <SheetContent side="left" class="w-72 p-0">
          <SheetTitle class="sr-only">Navigation</SheetTitle>
          <div class="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
            <Hexagon class="size-6 text-sidebar-primary" />
            <span class="text-base font-semibold tracking-tight">Kartograph</span>
          </div>

          <!-- Tenant Selector (Mobile Sidebar) -->
          <div
            class="border-b border-sidebar-border px-2 py-2"
            role="region"
            :aria-label="tenantAriaLabel"
          >
            <!-- Loading state -->
            <div
              v-if="tenantsLoading"
              class="flex items-center gap-2 rounded-md px-2 py-2"
              role="status"
              aria-live="polite"
            >
              <Loader2 class="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden="true" />
              <span class="text-sm text-muted-foreground">Loading...</span>
            </div>

            <!-- Zero tenants -->
            <NuxtLink
              v-else-if="tenantsLoaded && tenants.length === 0"
              to="/tenants"
              class="flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-2 transition-colors hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/50 dark:hover:bg-amber-950"
              :aria-label="tenantAriaLabel"
              @click="closeMobile"
            >
              <AlertTriangle class="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
              <span class="text-sm font-medium text-amber-700 dark:text-amber-300">No tenants — create one</span>
            </NuxtLink>

            <!-- Single tenant (static display) -->
            <div
              v-else-if="isSingleTenant"
              class="flex items-center gap-2 rounded-md bg-sidebar-accent px-2 py-2"
              role="status"
              :aria-label="tenantAriaLabel"
            >
              <Building2 class="size-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
              <span class="text-sm font-medium text-sidebar-foreground truncate">{{ selectedTenantName }}</span>
            </div>

            <!-- Multiple tenants: DropdownMenu-based picker (Token 5: "Manage Tenants" link) -->
            <DropdownMenu v-else>
              <DropdownMenuTrigger as-child>
                <button
                  class="flex w-full items-center gap-2 rounded-md bg-sidebar-accent px-2 py-2 text-left transition-colors hover:bg-sidebar-accent/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                  :aria-label="tenantAriaLabel"
                >
                  <Building2 class="size-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
                  <span class="flex-1 truncate text-sm font-medium text-sidebar-foreground">
                    {{ selectedTenantName ?? 'Select tenant...' }}
                  </span>
                  <ChevronsUpDown class="size-4 shrink-0 text-sidebar-foreground/50" aria-hidden="true" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent class="w-56" side="bottom" align="start" :side-offset="4">
                <DropdownMenuLabel class="text-xs text-muted-foreground">
                  Switch tenant
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  v-for="tenant in tenants"
                  :key="tenant.id"
                  class="flex items-center gap-2"
                  @click="handleTenantChange(tenant.id)"
                >
                  <Building2 class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span class="flex-1 truncate">{{ tenant.name }}</span>
                  <Check
                    v-if="tenant.id === currentTenantId"
                    class="size-4 shrink-0 text-sidebar-primary"
                    aria-hidden="true"
                  />
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem as-child>
                  <NuxtLink to="/tenants" class="flex items-center gap-2" @click="closeMobile">
                    <Settings2 class="size-4 shrink-0 text-muted-foreground" />
                    <span>Manage Tenants</span>
                  </NuxtLink>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <nav class="flex-1 overflow-y-auto py-3" aria-label="Main navigation">
            <!-- Home item (mobile) -->
            <div class="mb-3 px-2">
              <div class="space-y-0.5">
                <NuxtLink
                  :to="homeItem.to"
                  :class="[
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                    isActive(homeItem.to)
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                      : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                  ]"
                  @click="closeMobile"
                >
                  <component :is="homeItem.icon" class="size-4 shrink-0" />
                  <span>{{ homeItem.label }}</span>
                </NuxtLink>
              </div>
            </div>

            <!-- Nav sections (mobile) -->
            <div v-for="section in navSections" :key="section.title" class="mb-3">
              <div class="mb-1 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {{ section.title }}
              </div>
              <div class="space-y-0.5 px-2">
                <template v-for="item in section.items" :key="item.to + item.label">
                  <!-- Disabled item (mobile) -->
                  <div
                    v-if="item.disabled"
                    class="flex items-center gap-3 rounded-md px-3 py-2 text-sm opacity-50 cursor-not-allowed text-sidebar-foreground/70"
                  >
                    <component :is="item.icon" class="size-4 shrink-0" />
                    <span>{{ item.label }}</span>
                    <Badge v-if="item.badge" variant="secondary" class="ml-auto text-[10px] px-1.5 py-0">
                      {{ item.badge }}
                    </Badge>
                  </div>
                  <!-- Normal item (mobile) -->
                  <NuxtLink
                    v-else
                    :to="item.to"
                    :class="[
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                      isActive(item.to)
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                        : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                    ]"
                    @click="closeMobile"
                  >
                    <component :is="item.icon" class="size-4 shrink-0" />
                    <span>{{ item.label }}</span>
                  </NuxtLink>
                </template>
              </div>
            </div>
          </nav>
        </SheetContent>
      </Sheet>

      <!-- Main Content Area -->
      <div class="flex flex-1 flex-col overflow-hidden">
        <!-- Header -->
        <header class="flex h-14 items-center gap-4 border-b border-border bg-background px-4">
          <!-- Mobile menu button -->
          <Button
            variant="ghost"
            size="icon"
            class="md:hidden"
            aria-label="Open navigation menu"
            @click="isMobileOpen = true"
          >
            <Menu class="size-5" />
          </Button>

          <!-- Mobile tenant indicator (visible only on mobile, shows current tenant inline) -->
          <div
            class="flex items-center gap-1.5 md:hidden min-w-0"
            role="status"
            :aria-label="tenantAriaLabel"
          >
            <Building2 class="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span v-if="tenantsLoading" class="text-sm text-muted-foreground truncate">Loading...</span>
            <span v-else-if="selectedTenantName" class="text-sm font-medium truncate">{{ selectedTenantName }}</span>
            <span v-else-if="tenantsLoaded && tenants.length === 0" class="text-sm text-amber-600 dark:text-amber-400 truncate">No tenant</span>
          </div>

          <!-- Breadcrumbs (Token 4) -->
          <nav v-if="breadcrumbs.length > 1" class="hidden md:flex items-center gap-1.5 text-sm" aria-label="Breadcrumb">
            <template v-for="(crumb, i) in breadcrumbs" :key="i">
              <ChevronRight v-if="i > 0" class="size-3.5 text-muted-foreground" />
              <NuxtLink v-if="crumb.to" :to="crumb.to" class="text-muted-foreground hover:text-foreground transition-colors">
                {{ crumb.label }}
              </NuxtLink>
              <span v-else class="text-foreground font-medium">{{ crumb.label }}</span>
            </template>
          </nav>

          <div class="flex-1" />

          <!-- Right side controls -->
          <div class="flex items-center gap-1">
            <!-- Dark mode toggle -->
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="ghost" size="icon" @click="toggleColorMode">
                  <Sun v-if="isDark" class="size-4" />
                  <Moon v-else class="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {{ isDark ? 'Switch to light mode' : 'Switch to dark mode' }}
              </TooltipContent>
            </Tooltip>

            <!-- User dropdown -->
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button variant="ghost" class="gap-2 px-2">
                  <Avatar class="size-7">
                    <AvatarFallback class="text-xs">{{ avatarInitials }}</AvatarFallback>
                  </Avatar>
                  <span class="hidden text-sm sm:inline">{{ displayName }}</span>
                  <ChevronDown class="size-3 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" class="w-48">
                <DropdownMenuLabel>
                  <div class="flex flex-col">
                    <span class="text-sm font-medium">{{ displayName }}</span>
                    <span class="text-xs text-muted-foreground">{{ displayEmail }}</span>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                  @click="handleLogout"
                >
                  <LogOut class="mr-2 size-4" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <!-- Page Content -->
        <main class="flex-1 overflow-y-auto p-6">
          <slot />
        </main>
      </div>
    </div>
  </TooltipProvider>
</template>
