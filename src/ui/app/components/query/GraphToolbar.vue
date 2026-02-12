<script setup lang="ts">
import { ref } from 'vue'
import { Maximize, Maximize2, Minimize2, Search, X, LayoutGrid } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = defineProps<{
  layout: string
  nodeCount: number
  edgeCount: number
  fullscreen: boolean
}>()

const emit = defineEmits<{
  'layout-change': [layout: string]
  'zoom-fit': []
  'search': [query: string]
  'toggle-fullscreen': []
}>()

const searchQuery = ref('')
const searchVisible = ref(false)

function handleSearch() {
  emit('search', searchQuery.value)
}

function clearSearch() {
  searchQuery.value = ''
  emit('search', '')
  searchVisible.value = false
}

function toggleSearch() {
  searchVisible.value = !searchVisible.value
  if (!searchVisible.value) {
    clearSearch()
  }
}
</script>

<template>
  <div class="flex items-center justify-between border-b px-3 py-1.5">
    <div class="flex items-center gap-2">
      <!-- Layout selector -->
      <div class="flex items-center gap-1.5">
        <LayoutGrid class="size-3.5 text-muted-foreground" />
        <Select
          :model-value="props.layout"
          @update:model-value="(v: string) => emit('layout-change', v)"
        >
          <SelectTrigger class="h-7 w-[160px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="fcose">Force Directed</SelectItem>
            <SelectItem value="cise-label">Clustered (by type)</SelectItem>
            <SelectItem value="cise-mcl">Clustered (topology)</SelectItem>
            <SelectItem value="breadthfirst">Hierarchical</SelectItem>
            <SelectItem value="concentric">Concentric</SelectItem>
            <SelectItem value="grid">Grid</SelectItem>
            <SelectItem value="circle">Circle</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <!-- Zoom to fit -->
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="ghost"
            size="icon"
            class="size-7"
            aria-label="Fit graph to viewport"
            @click="emit('zoom-fit')"
          >
            <Maximize class="size-3.5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p>Fit to viewport</p>
        </TooltipContent>
      </Tooltip>

      <!-- Fullscreen toggle -->
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="ghost"
            size="icon"
            class="size-7"
            aria-label="Toggle fullscreen"
            @click="emit('toggle-fullscreen')"
          >
            <Minimize2 v-if="props.fullscreen" class="size-3.5" />
            <Maximize2 v-else class="size-3.5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p>{{ props.fullscreen ? 'Exit fullscreen' : 'Fullscreen' }}</p>
        </TooltipContent>
      </Tooltip>

      <!-- Search toggle -->
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="ghost"
            size="icon"
            class="size-7"
            :class="searchVisible ? 'bg-muted' : ''"
            aria-label="Search nodes"
            @click="toggleSearch"
          >
            <Search class="size-3.5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p>Search nodes</p>
        </TooltipContent>
      </Tooltip>

      <!-- Search input -->
      <div v-if="searchVisible" class="flex items-center gap-1">
        <Input
          v-model="searchQuery"
          placeholder="Find node..."
          class="h-7 w-40 text-xs"
          autofocus
          @input="handleSearch"
          @keydown.enter="handleSearch"
          @keydown.escape="clearSearch"
        />
        <Tooltip>
          <TooltipTrigger as-child>
            <Button
              v-if="searchQuery"
              variant="ghost"
              size="icon"
              class="size-6"
              aria-label="Clear search"
              @click="clearSearch"
            >
              <X class="size-3" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <p>Clear search</p>
          </TooltipContent>
        </Tooltip>
      </div>
    </div>

    <!-- Stats -->
    <div class="flex items-center gap-2">
      <Badge variant="secondary" class="h-5 px-1.5 font-mono text-[10px]">
        {{ nodeCount.toLocaleString() }} nodes
      </Badge>
      <Badge variant="secondary" class="h-5 px-1.5 font-mono text-[10px]">
        {{ edgeCount.toLocaleString() }} edges
      </Badge>
    </div>
  </div>
</template>
