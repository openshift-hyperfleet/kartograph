<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
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
  Hexagon,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useSidebar } from '@/composables/useSidebar'
import { useColorMode } from '@/composables/useColorMode'
import type { TenantResponse } from '~/types'

const route = useRoute()
const { isCollapsed, isMobileOpen, toggleCollapsed, closeMobile } = useSidebar()
const { isDark, toggle: toggleColorMode } = useColorMode()

// ── Auth & Tenant state ────────────────────────────────────────────────────
const { user, logout } = useAuth()
const { listTenants } = useIamApi()
const { currentTenantId } = useApiClient()

const tenants = ref<TenantResponse[]>([])
const selectedTenantId = ref<string>('')

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

// Sync selected tenant to the API client's currentTenantId
watch(selectedTenantId, (id) => {
  currentTenantId.value = id || null
})

async function fetchTenants() {
  try {
    tenants.value = await listTenants()
    // Auto-select first tenant if none selected
    if (tenants.value.length > 0 && !selectedTenantId.value) {
      selectedTenantId.value = tenants.value[0].id
    }
  } catch (err) {
    toast.error('Failed to load tenants', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
  }
}

async function handleLogout() {
  try {
    await logout()
  } catch (err) {
    toast.error('Logout failed')
  }
}

onMounted(fetchTenants)

interface NavItem {
  label: string
  icon: typeof Building2
  to: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    title: 'Identity',
    items: [
      { label: 'Tenants', icon: Building2, to: '/tenants' },
      { label: 'Workspaces', icon: FolderTree, to: '/workspaces' },
      { label: 'Groups', icon: Users, to: '/groups' },
      { label: 'API Keys', icon: KeyRound, to: '/api-keys' },
    ],
  },
  {
    title: 'Graph',
    items: [
      { label: 'Schema Browser', icon: Database, to: '/graph/schema' },
      { label: 'Explorer', icon: Share2, to: '/graph/explorer' },
      { label: 'Mutations', icon: FileCode, to: '/graph/mutations' },
    ],
  },
  {
    title: 'Query',
    items: [
      { label: 'Cypher Console', icon: Terminal, to: '/query' },
    ],
  },
]

function isActive(to: string): boolean {
  return route.path === to
}

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

        <!-- Navigation -->
        <nav class="flex-1 overflow-y-auto py-3">
          <div v-for="section in navSections" :key="section.title" class="mb-3">
            <div
              v-if="!isCollapsed"
              class="mb-1 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              {{ section.title }}
            </div>
            <Separator v-else class="mx-auto mb-2 w-8" />

            <div class="space-y-0.5 px-2">
              <template v-for="item in section.items" :key="item.to">
                <Tooltip v-if="isCollapsed">
                  <TooltipTrigger as-child>
                    <NuxtLink
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
                    {{ item.label }}
                  </TooltipContent>
                </Tooltip>

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

          <nav class="flex-1 overflow-y-auto py-3">
            <div v-for="section in navSections" :key="section.title" class="mb-3">
              <div class="mb-1 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {{ section.title }}
              </div>
              <div class="space-y-0.5 px-2">
                <NuxtLink
                  v-for="item in section.items"
                  :key="item.to"
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
            @click="isMobileOpen = true"
          >
            <Menu class="size-5" />
          </Button>

          <!-- Tenant selector -->
          <div class="flex items-center gap-2">
            <Select v-model="selectedTenantId">
              <SelectTrigger class="w-48">
                <SelectValue placeholder="Select tenant..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="tenant in tenants"
                  :key="tenant.id"
                  :value="tenant.id"
                >
                  {{ tenant.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

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
